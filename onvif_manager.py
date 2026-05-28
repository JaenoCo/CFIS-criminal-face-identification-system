"""
ONVIF camera discovery and stream manager for the Security Face Detection System.
Allows detecting ONVIF-enabled cameras on the network and retrieving their RTSP streams.
"""

import threading
import json
import os
import sys
import socket
from typing import List, Optional
import logging
from urllib.parse import quote

import cv2

logger = logging.getLogger(__name__)

try:
    from onvif import ONVIFCamera
    ONVIF_AVAILABLE = True
except ImportError:
    ONVIF_AVAILABLE = False
    logger.warning("onvif-zeep not installed. ONVIF discovery will be unavailable.")


class ONVIFDevice:
    """Represents a discovered ONVIF device."""
    
    def __init__(self, ip: str, port: int = 8080, username: str = "", password: str = ""):
        self.ip = ip
        self.port = port
        self.username = username
        self.password = password
        self.is_manual = False
        self.hostname = None
        self.manufacturer = None
        self.model = None
        self.firmware_version = None
        self.stream_uri = None
        self.stream_channels: List[str] = []
        self.selected_channel = 0
        self.connected = False
        
    def to_string(self) -> str:
        """Return human-readable device info."""
        info = f"{self.hostname or self.ip} ({self.manufacturer} {self.model})"
        return info
    
    def __repr__(self):
        return f"ONVIFDevice({self.ip}:{self.port})"


class ONVIFManager:
    """Manages ONVIF device discovery and stream retrieval."""
    
    def __init__(self):
        self.devices: List[ONVIFDevice] = []
        self.discovering = False
        self._discovery_thread = None
        self._storage_path = self._get_storage_path()
        self._load_manual_devices()

    @staticmethod
    def _runtime_base_dir() -> str:
        if getattr(sys, "frozen", False):
            return os.path.dirname(os.path.abspath(sys.executable))
        return os.path.dirname(os.path.abspath(__file__))

    def _get_storage_path(self) -> str:
        return os.path.join(self._runtime_base_dir(), "temp", "onvif_manual_devices.json")

    @staticmethod
    def _detect_local_subnet(default_subnet: str = "192.168.1") -> str:
        """Detect local IPv4 /24 subnet prefix (e.g. '192.168.1')."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                # No packets are sent, this only asks OS routing for the outbound interface.
                sock.connect(("8.8.8.8", 80))
                local_ip = sock.getsockname()[0]
            finally:
                sock.close()

            parts = local_ip.split(".")
            if len(parts) == 4:
                return ".".join(parts[:3])
        except Exception:
            pass
        return default_subnet

    def _load_manual_devices(self):
        if not os.path.exists(self._storage_path):
            return
        try:
            with open(self._storage_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except Exception as exc:
            logger.warning(f"Unable to load ONVIF manual devices: {exc}")
            return

        if not isinstance(payload, list):
            return

        for item in payload:
            if not isinstance(item, dict):
                continue
            ip = str(item.get("ip", "")).strip()
            if not ip:
                continue
            try:
                port = int(item.get("port", 8080))
            except (TypeError, ValueError):
                port = 8080

            device = ONVIFDevice(
                ip=ip,
                port=port,
                username=str(item.get("username", "") or ""),
                password=str(item.get("password", "") or ""),
            )
            device.is_manual = True
            stream_uri = str(item.get("stream_uri", "") or "").strip()
            if stream_uri:
                device.stream_uri = stream_uri
            stream_channels = item.get("stream_channels", [])
            if isinstance(stream_channels, list):
                device.stream_channels = [str(uri) for uri in stream_channels if str(uri).strip()]
            selected_channel = item.get("selected_channel", 0)
            if isinstance(selected_channel, int) and selected_channel >= 0:
                device.selected_channel = selected_channel
            self.devices.append(device)

    def _save_manual_devices(self):
        manual_devices = [device for device in self.devices if getattr(device, "is_manual", False)]
        payload = []
        for device in manual_devices:
            payload.append(
                {
                    "ip": device.ip,
                    "port": device.port,
                    "username": device.username,
                    "password": device.password,
                    "stream_uri": device.stream_uri,
                    "stream_channels": list(device.stream_channels or []),
                    "selected_channel": int(device.selected_channel or 0),
                }
            )

        try:
            os.makedirs(os.path.dirname(self._storage_path), exist_ok=True)
            with open(self._storage_path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2)
        except Exception as exc:
            logger.warning(f"Unable to save ONVIF manual devices: {exc}")

    @staticmethod
    def _create_camera(ip: str, port: int, username: str, password: str):
        return ONVIFCamera(
            ip,
            port,
            username or "",
            password or "",
        )

    @staticmethod
    def _build_rtsp_candidates(ip: str, port: int, username: str = "", password: str = "") -> List[str]:
        host = f"{ip}:{port}" if port else ip
        auth = ""
        if username:
            safe_username = quote(username, safe="")
            safe_password = quote(password or "", safe="")
            auth = f"{safe_username}:{safe_password}@"

        templates = [
            "rtsp://{auth}{host}/live/ch00_0",
            "rtsp://{auth}{host}/live/ch00_1",
            "rtsp://{auth}{host}/stream1",
            "rtsp://{auth}{host}/stream0",
            "rtsp://{auth}{ip}/live/ch00_0",
            "rtsp://{auth}{ip}/live/ch00_1",
            "rtsp://{auth}{ip}/stream1",
            "rtsp://{auth}{ip}/stream0",
        ]

        candidates = []
        for template in templates:
            candidate = template.format(auth=auth, host=host, ip=ip)
            if candidate not in candidates:
                candidates.append(candidate)
        return candidates

    @staticmethod
    def _rtsp_stream_works(stream_uri: str) -> bool:
        capture = cv2.VideoCapture(stream_uri)
        try:
            # Keep probe latency bounded when URI is unreachable.
            if hasattr(cv2, "CAP_PROP_OPEN_TIMEOUT_MSEC"):
                capture.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 2500)
            if hasattr(cv2, "CAP_PROP_READ_TIMEOUT_MSEC"):
                capture.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 2500)

            if not capture.isOpened():
                return False

            for _ in range(4):
                ret, frame = capture.read()
                if ret and frame is not None and frame.size > 0:
                    return True
            return False
        except Exception:
            return False
        finally:
            capture.release()

    @staticmethod
    def _derive_companion_channels(stream_uri: str) -> List[str]:
        """Populate common paired V380 channels when one stream URI is known."""
        uri = str(stream_uri or "").strip()
        if not uri:
            return []

        channels = [uri]
        pairs = [
            ("/live/ch00_0", "/live/ch00_1"),
            ("/live/ch00_1", "/live/ch00_0"),
            ("/stream0", "/stream1"),
            ("/stream1", "/stream0"),
        ]
        for source_suffix, target_suffix in pairs:
            if uri.endswith(source_suffix):
                sibling = f"{uri[:-len(source_suffix)]}{target_suffix}"
                if sibling not in channels:
                    channels.append(sibling)
                break
        return channels

    def _resolve_rtsp_stream(self, device: ONVIFDevice) -> Optional[str]:
        candidates = []
        if device.stream_uri:
            candidates.append(device.stream_uri)
        for candidate in self._build_rtsp_candidates(device.ip, device.port, device.username, device.password):
            if candidate not in candidates:
                candidates.append(candidate)

        for candidate in candidates:
            try:
                if self._rtsp_stream_works(candidate):
                    device.stream_uri = candidate
                    device.stream_channels = [candidate]
                    device.selected_channel = 0
                    device.connected = True
                    if device.is_manual:
                        self._save_manual_devices()
                    return candidate
            except Exception as exc:
                logger.debug(f"RTSP probe failed for {candidate}: {exc}")

        return None
    
    def discover_devices_background(self, callback=None, subnet=None, timeout=3):
        """
        Start background discovery of ONVIF devices on the network.
        
        Args:
            callback: Optional function to call with discovered devices list
            subnet: Network subnet to scan (e.g., "192.168.1"). Auto-detected when None.
            timeout: Timeout per IP in seconds
        """
        if not ONVIF_AVAILABLE:
            if callback:
                callback([])
            return
        
        self._discovery_thread = threading.Thread(
            target=self._discover_devices,
            args=(callback, subnet, timeout),
            daemon=True
        )
        self._discovery_thread.start()
    
    def _discover_devices(self, callback=None, subnet=None, timeout=3):
        """Internal method to discover devices."""
        self.discovering = True
        subnet_prefix = subnet or self._detect_local_subnet()
        manual_devices = [device for device in self.devices if getattr(device, "is_manual", False)]
        self.devices = list(manual_devices)
        
        try:
            # Scan common IP range
            for i in range(1, 256):
                if not self.discovering:
                    break
                    
                ip = f"{subnet_prefix}.{i}"
                
                # Try common ONVIF/RTSP ports (including V380 variants)
                for port in [8080, 80, 8000, 8899, 554]:
                    try:
                        device = self._probe_device(ip, port, "", "", timeout)
                        if device:
                            if any(existing.ip == device.ip and existing.port == device.port for existing in self.devices):
                                break
                            self.devices.append(device)
                            logger.info(f"Found ONVIF device: {device}")
                            break
                    except Exception:
                        continue
        
        except Exception as e:
            logger.error(f"Discovery error: {e}")
        
        finally:
            self.discovering = False
            if callback:
                callback(self.devices)
    
    def _probe_device(
        self,
        ip: str,
        port: int,
        username: str,
        password: str,
        timeout: float,
        require_stream: bool = True,
    ) -> Optional[ONVIFDevice]:
        """Probe a single IP address for ONVIF service."""
        try:
            device = ONVIFDevice(ip, port, username, password)
            probe_succeeded = False

            camera = self._create_camera(ip, port, username, password)
            
            # Get device info
            try:
                device_info = camera.devicemgmt.GetDeviceInformation()
                device.manufacturer = device_info.Manufacturer
                device.model = device_info.Model
                device.firmware_version = device_info.FirmwareVersion
                probe_succeeded = True
            except Exception as e:
                logger.debug(f"Could not get device info for {ip}: {e}")
            
            # Get device hostname
            try:
                hostname_info = camera.devicemgmt.GetHostname()
                device.hostname = hostname_info.Hostname
                probe_succeeded = True
            except Exception as e:
                logger.debug(f"Could not get hostname for {ip}: {e}")
            
            # Get stream URI
            try:
                stream_channels = self._get_stream_channels(camera)
                if stream_channels:
                    device.stream_channels = stream_channels
                    device.stream_uri = stream_channels[0]
                    device.selected_channel = 0
                    device.connected = True
                    return device
            except Exception as e:
                logger.debug(f"Could not get stream URI for {ip}: {e}")

            if probe_succeeded and not require_stream:
                device.connected = True
                return device

            if port == 554 or not require_stream:
                resolved_stream = self._resolve_rtsp_stream(device)
                if resolved_stream:
                    return device
        
        except Exception as e:
            logger.debug(f"Failed to probe {ip}:{port} - {e}")
        
        return None
    
    @staticmethod
    def _get_stream_channels(camera) -> List[str]:
        """Get RTSP stream URIs for available media profiles."""
        try:
            media_service = camera.create_media_service()
            profiles = media_service.GetProfiles()

            if not profiles:
                return []

            channels = []
            for profile in profiles:
                try:
                    request = media_service.create_type("GetStreamUri")
                    request.ProfileToken = profile.token
                    request.StreamSetup = {
                        "Stream": "RTP-Unicast",
                        "Transport": {"Protocol": "RTSP"},
                    }
                    stream_info = media_service.GetStreamUri(request)
                    uri = getattr(stream_info, "Uri", None)
                    if uri and uri not in channels:
                        channels.append(uri)
                except Exception:
                    continue

            return channels

        except Exception as e:
            logger.error(f"Error getting stream URI: {e}")
            return []
    
    def add_device_manual(
        self,
        ip: str,
        port: int = 8080,
        username: str = "",
        password: str = "",
        stream_uri: str = "",
    ) -> Optional[ONVIFDevice]:
        """
        Manually add and probe a specific ONVIF device.
        
        Args:
            ip: IP address of the ONVIF device
            port: Port (default 8080)
            username: Username for authentication
            password: Password for authentication
        
        Returns:
            ONVIFDevice if successful, None otherwise
        """
        if not ONVIF_AVAILABLE:
            logger.warning("ONVIF not available — proceeding with RTSP-only manual add attempts")

        try:
            stream_uri = str(stream_uri or "").strip()

            candidate_ports = []
            for candidate_port in [port, 80, 8080, 8000, 8899, 554]:
                if candidate_port not in candidate_ports:
                    candidate_ports.append(candidate_port)

            if stream_uri:
                device = ONVIFDevice(ip, port, username, password)
                device.is_manual = True
                device.stream_uri = stream_uri
                device.stream_channels = self._derive_companion_channels(stream_uri)
                device.connected = True

                for existing in list(self.devices):
                    if existing.ip == device.ip:
                        self.devices.remove(existing)
                        break
                self.devices.append(device)
                self._save_manual_devices()
                return device

            # If ONVIF is not available, attempt RTSP candidate probing directly
            if not ONVIF_AVAILABLE:
                device = ONVIFDevice(ip, port, username, password)
                device.is_manual = True
                resolved = self._resolve_rtsp_stream(device)
                if resolved:
                    for existing in list(self.devices):
                        if existing.ip == device.ip:
                            self.devices.remove(existing)
                            break
                    self.devices.append(device)
                    self._save_manual_devices()
                    return device
                return None

            for candidate_port in candidate_ports:
                device = self._probe_device(
                    ip,
                    candidate_port,
                    username,
                    password,
                    timeout=5,
                    require_stream=False,
                )
                if not device:
                    continue

                device.is_manual = True
                if not device.stream_uri:
                    self._resolve_rtsp_stream(device)

                for existing in list(self.devices):
                    if existing.ip == device.ip:
                        self.devices.remove(existing)
                        break
                self.devices.append(device)
                self._save_manual_devices()
                return device

            return None
        except Exception as e:
            logger.error(f"Failed to add device {ip}: {e}")
            return None
    
    def stop_discovery(self):
        """Stop any ongoing discovery."""
        self.discovering = False
    
    def get_device_stream_channels(self, device: ONVIFDevice) -> List[str]:
        """Get all available stream channels for a device."""
        if device.stream_channels:
            return device.stream_channels

        try:
            if ONVIF_AVAILABLE:
                camera = self._create_camera(
                    device.ip,
                    device.port,
                    device.username,
                    device.password,
                )
                channels = self._get_stream_channels(camera)
                if channels:
                    device.stream_channels = channels
                    if device.selected_channel >= len(channels):
                        device.selected_channel = 0
                    device.stream_uri = channels[device.selected_channel]
                    device.connected = True
                    if device.is_manual:
                        self._save_manual_devices()
                    return channels
        except Exception as e:
            logger.error(f"Failed to get stream channels for {device}: {e}")

        return []

    def get_device_stream(self, device: ONVIFDevice, channel_index: Optional[int] = None) -> Optional[str]:
        """Get stream URI for a device, optionally by channel index."""
        channels = self.get_device_stream_channels(device)
        if channels:
            selected_idx = device.selected_channel if channel_index is None else channel_index
            if selected_idx < 0 or selected_idx >= len(channels):
                selected_idx = 0
            device.selected_channel = selected_idx
            device.stream_uri = channels[selected_idx]
            if device.is_manual:
                self._save_manual_devices()
            return device.stream_uri

        if device.stream_uri:
            return device.stream_uri

        resolved_stream = self._resolve_rtsp_stream(device)
        if resolved_stream:
            return resolved_stream
        
        # Try to retrieve if not cached
        try:
            if ONVIF_AVAILABLE:
                camera = self._create_camera(
                    device.ip,
                    device.port,
                    device.username,
                    device.password,
                )
                channels = self._get_stream_channels(camera)
                if channels:
                    device.stream_channels = channels
                    device.selected_channel = 0
                    device.stream_uri = channels[0]
                    if device.is_manual:
                        self._save_manual_devices()
                    return device.stream_uri
        except Exception as e:
            logger.error(f"Failed to get stream for {device}: {e}")
        
        return None
