import os
import re
import socket
import logging
import concurrent.futures
from typing import Dict, Any, List, Optional, Tuple
from urllib.parse import urlparse, urlunparse
import cv2
import requests
import urllib3
from requests.auth import HTTPDigestAuth, HTTPBasicAuth

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logger = logging.getLogger(__name__)

CANDIDATE_RTSP_PORTS = [554, 8554, 5544, 10554]
CANDIDATE_HTTP_PORTS = [(443, "https"), (80, "http"), (8080, "http"), (8000, "http"), (8899, "http")]

FALLBACK_PATHS = [
    "/video/live?channel=1&subtype=1&unicast=true&proto=Onvif&tls=true",
    "/video/live?channel=1&subtype=0&unicast=true&proto=Onvif&tls=true",
    "/video/live?channel=1&subtype=1",
    "/video/live?channel=1&subtype=0",
    "/cam/realmonitor?channel=1&subtype=1",
    "/cam/realmonitor?channel=1&subtype=0",
    "/live/ch0",
    "/live/ch1",
    "/stream1",
    "/stream2",
    "/h264/ch1/sub/av_stream",
    "/h264/ch1/main/av_stream",
    "/Streaming/Channels/102",
    "/Streaming/Channels/101",
]


def is_port_open(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        res = s.connect_ex((host, port))
        s.close()
        return res == 0
    except Exception:
        return False


def _soap_post(url: str, body_xml: str, username: str, password: str, timeout: float = 3.0) -> Optional[str]:
    soap = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope">'
        f"<s:Body>{body_xml}</s:Body>"
        "</s:Envelope>"
    )
    headers = {"Content-Type": "application/soap+xml; charset=utf-8"}
    for auth in (HTTPDigestAuth(username, password), HTTPBasicAuth(username, password), None):
        try:
            r = requests.post(url, data=soap, auth=auth, headers=headers, timeout=timeout, verify=False)
            if r.status_code == 200 and "<" in r.text:
                return r.text
        except Exception:
            continue
    return None


def query_onvif_camera(ip: str, username: str, password: str) -> Dict[str, Any]:
    """
    Auto-discovers ONVIF device service across HTTPS/HTTP ports, retrieves manufacturer/model,
    media service URL, profile tokens, and exact RTSP/RTSPS stream URIs.
    """
    info: Dict[str, Any] = {
        "manufacturer": None,
        "model": None,
        "stream_uris": [],  # list of (subtype_hint, uri)
    }

    device_service_url = None
    for port, scheme in CANDIDATE_HTTP_PORTS:
        if not is_port_open(ip, port, timeout=0.5):
            continue
        candidate = f"{scheme}://{ip}:{port}/onvif/device_service"
        resp = _soap_post(
            candidate,
            '<tds:GetDeviceInformation xmlns:tds="http://www.onvif.org/ver10/device/wsdl"/>',
            username,
            password,
        )
        if resp:
            device_service_url = candidate
            m_man = re.search(r"<[^:>]*:?Manufacturer[^>]*>([^<]+)</", resp)
            m_mod = re.search(r"<[^:>]*:?Model[^>]*>([^<]+)</", resp)
            if m_man:
                info["manufacturer"] = m_man.group(1).strip()
            if m_mod:
                info["model"] = m_mod.group(1).strip()
            break

    if not device_service_url:
        return info

    # Get Media service XAddr
    cap_resp = _soap_post(
        device_service_url,
        '<tds:GetCapabilities xmlns:tds="http://www.onvif.org/ver10/device/wsdl"><tds:Category>Media</tds:Category></tds:GetCapabilities>',
        username,
        password,
    )
    if not cap_resp:
        return info

    media_urls = [u.strip() for u in re.findall(r"<[^:>]*:?XAddr[^>]*>([^<]+)</", cap_resp) if "media" in u.lower()]
    if not media_urls:
        return info
    media_url = media_urls[0]

    # Get Profiles
    prof_resp = _soap_post(
        media_url,
        '<trt:GetProfiles xmlns:trt="http://www.onvif.org/ver10/media/wsdl"/>',
        username,
        password,
    )
    if not prof_resp:
        return info

    # Extract profile tokens (unique, ordered)
    raw_tokens = re.findall(r'<[^:>]*:?Profiles[^>]*token="([^"]+)"', prof_resp)
    if not raw_tokens:
        raw_tokens = re.findall(r'token="(MediaProfile[^"]+)"', prof_resp)
    tokens = list(dict.fromkeys(raw_tokens))[:4]

    for idx, token in enumerate(tokens):
        uri_resp = _soap_post(
            media_url,
            f'<trt:GetStreamUri xmlns:trt="http://www.onvif.org/ver10/media/wsdl">'
            f'<trt:StreamSetup><tt:Stream xmlns:tt="http://www.onvif.org/ver10/schema">RTP-Unicast</tt:Stream>'
            f'<tt:Transport xmlns:tt="http://www.onvif.org/ver10/schema"><tt:Protocol>RTSP</tt:Protocol></tt:Transport>'
            f'</trt:StreamSetup><trt:ProfileToken>{token}</trt:ProfileToken></trt:GetStreamUri>',
            username,
            password,
        )
        if not uri_resp:
            continue
        uris = re.findall(r"<[^:>]*:?Uri[^>]*>(rtsps?://[^<]+)</", uri_resp)
        for u in uris:
            clean_u = u.replace("&amp;", "&").strip()
            if clean_u:
                info["stream_uris"].append((str(idx), clean_u))

    return info


def _inject_credentials(uri: str, username: str, password: str, force_rtsps: bool = False) -> Tuple[str, str, int, str]:
    parsed = urlparse(uri)
    scheme = "rtsps" if (force_rtsps or "tls=true" in (parsed.query or "").lower()) else (parsed.scheme or "rtsp")
    port = parsed.port or 554
    host = parsed.hostname or ""
    path_with_query = parsed.path + (f"?{parsed.query}" if parsed.query else "")
    full_url = f"{scheme}://{username}:{password}@{host}:{port}{path_with_query}"
    return full_url, scheme, port, path_with_query


def _test_stream_url(url: str, timeout_us: int = 3500000) -> bool:
    os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = f"rtsp_transport;tcp|stimeout;{timeout_us}"
    try:
        cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        if cap.isOpened():
            ret, frame = cap.read()
            cap.release()
            return bool(ret and frame is not None and frame.size > 0)
        cap.release()
    except Exception:
        pass
    return False


def auto_detect_camera(ip: str, username: str, password: str, preferred_subtype: str = "1") -> Dict[str, Any]:
    """
    Fully automatic onboarding for any IP camera:
    1. Queries ONVIF for exact model, port, protocol (rtsps/rtsp), and stream paths.
    2. Falls back to probing open RTSP ports & common stream paths.
    3. Verifies a real video frame can be decoded before returning.
    """
    ip = ip.strip()
    onvif = query_onvif_camera(ip, username, password)
    candidates: List[Tuple[str, str, int, str]] = []

    # 1. Prioritize ONVIF-reported URIs matching preferred subtype (sub stream '1' vs main '0')
    onvif_uris = onvif.get("stream_uris", [])
    ordered_onvif = sorted(
        onvif_uris,
        key=lambda item: (
            0 if f"subtype={preferred_subtype}" in item[1] or item[0] == preferred_subtype else 1,
            0 if "subtype=1" in item[1] else 1,
        ),
    )

    for _, raw_uri in ordered_onvif:
        has_tls = "tls=true" in raw_uri.lower()
        candidates.append(_inject_credentials(raw_uri, username, password, force_rtsps=has_tls))
        if has_tls:
            candidates.append(_inject_credentials(raw_uri, username, password, force_rtsps=False))

    # 2. Scan open RTSP ports and add fallback paths
    open_ports = [p for p in CANDIDATE_RTSP_PORTS if is_port_open(ip, p, timeout=0.5)]
    if not open_ports:
        open_ports = [554]

    for port in open_ports:
        for path in FALLBACK_PATHS:
            scheme = "rtsps" if "tls=true" in path else "rtsp"
            full_url = f"{scheme}://{username}:{password}@{ip}:{port}{path}"
            candidates.append((full_url, scheme, port, path))

    # Deduplicate candidates while keeping priority order
    seen = set()
    unique_candidates = []
    for c in candidates:
        if c[0] not in seen:
            seen.add(c[0])
            unique_candidates.append(c)

    # 3. Verify live frame decode on first working candidate
    for full_url, scheme, port, path in unique_candidates:
        logger.info(f"[AutoDetect {ip}] Testing {scheme}://{ip}:{port}{path}")
        if _test_stream_url(full_url):
            logger.info(f"[AutoDetect {ip}] LOCKED {scheme}://{ip}:{port}{path}")
            return {
                "success": True,
                "ip": ip,
                "port": port,
                "protocol": scheme,
                "stream_path": path,
                "subtype": preferred_subtype,
                "manufacturer": onvif.get("manufacturer") or "IP Camera",
                "model": onvif.get("model") or "Auto-Detected",
                "message": f"Connected via {scheme.upper()} on port {port}",
            }

    return {
        "success": False,
        "ip": ip,
        "port": open_ports[0],
        "protocol": "rtsps",
        "stream_path": f"/video/live?channel=1&subtype={preferred_subtype}&unicast=true&proto=Onvif&tls=true",
        "subtype": preferred_subtype,
        "manufacturer": onvif.get("manufacturer"),
        "model": onvif.get("model"),
        "message": (
            f"Could not open live stream on {ip}. Check IP, credentials, or ONVIF/RTSP settings on the camera."
        ),
    }


def discover_lan_cameras() -> List[Dict[str, Any]]:
    """
    Discovers IP cameras on all local IPv4 subnets using both:
    - ONVIF WS-Discovery UDP multicast (port 3702)
    - Parallel TCP port scan for RTSP ports (554, 8554)
    """
    discovered: Dict[str, Dict[str, Any]] = {}

    # Collect local subnets (e.g. 192.168.0.x, 192.168.1.x)
    local_ips = set()
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            addr = info[4][0]
            if not addr.startswith("127.") and not addr.startswith("169.254.") and not addr.startswith("100."):
                local_ips.add(addr)
    except Exception:
        pass

    # 1. ONVIF WS-Discovery UDP Multicast on every local interface
    probe_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<e:Envelope xmlns:e="http://www.w3.org/2003/05/soap-envelope" '
        'xmlns:w="http://schemas.xmlsoap.org/ws/2004/08/addressing" '
        'xmlns:d="http://schemas.xmlsoap.org/ws/2005/04/discovery" '
        'xmlns:dn="http://www.onvif.org/ver10/network/wsdl">'
        '<e:Header><w:MessageID>uuid:12345678-1234-1234-1234-1234567890ab</w:MessageID>'
        '<w:To>urn:schemas-xmlsoap-org:ws:2005:04:discovery</w:To>'
        '<w:Action>http://schemas.xmlsoap.org/ws/2005/04/discovery/Probe</w:Action></e:Header>'
        '<e:Body><d:Probe><d:Types>dn:NetworkVideoTransmitter</d:Types></d:Probe></e:Body></e:Envelope>'
    )
    for iface in local_ips:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        try:
            s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(iface))
            s.settimeout(1.5)
            s.sendto(probe_xml.encode(), ("239.255.255.250", 3702))
            while True:
                try:
                    data, addr = s.recvfrom(8192)
                    cam_ip = addr[0]
                    discovered[cam_ip] = {
                        "ip": cam_ip,
                        "port": 554,
                        "method": "ONVIF Discovery",
                    }
                except socket.timeout:
                    break
        except Exception:
            pass
        finally:
            s.close()

    # 2. Fast parallel TCP scan on /24 prefixes of local interfaces (excluding Docker/vEthernet 172.x)
    prefixes = set()
    for addr in local_ips:
        if addr.startswith("192.168.") or addr.startswith("10."):
            prefixes.add(".".join(addr.split(".")[:3]))
    prefixes.update(["192.168.0", "192.168.1"])

    scan_ips = [f"{pref}.{i}" for pref in prefixes for i in range(1, 255)]

    def _scan_ip(ip: str):
        for p in (554, 8554):
            if is_port_open(ip, p, timeout=0.2):
                return (ip, p)
        return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=128) as ex:
        for res in ex.map(_scan_ip, scan_ips):
            if res:
                ip, port = res
                if ip not in discovered:
                    discovered[ip] = {"ip": ip, "port": port, "method": "RTSP Port Scan"}
                else:
                    discovered[ip]["port"] = port

    return sorted(discovered.values(), key=lambda d: d["ip"])
