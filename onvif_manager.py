"""
ONVIF camera discovery and stream manager for CFIS.
Allows detecting ONVIF-enabled cameras on the network and retrieving their RTSP streams.
"""

import threading
from typing import List, Optional
import logging

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
        self.hostname = None
        self.manufacturer = None
        self.model = None
        self.firmware_version = None
        self.stream_uri = None
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

    @staticmethod
    def _create_camera(ip: str, port: int, username: str, password: str):
        return ONVIFCamera(
            ip,
            port,
            username or "",
            password or "",
        )
    
    def discover_devices_background(self, callback=None, subnet="192.168.1", timeout=3):
        """
        Start background discovery of ONVIF devices on the network.
        
        Args:
            callback: Optional function to call with discovered devices list
            subnet: Network subnet to scan (e.g., "192.168.1")
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
    
    def _discover_devices(self, callback=None, subnet="192.168.1", timeout=3):
        """Internal method to discover devices."""
        self.discovering = True
        self.devices = []
        
        try:
            # Scan common IP range
            for i in range(1, 256):
                if not self.discovering:
                    break
                    
                ip = f"{subnet}.{i}"
                
                # Try common ONVIF/RTSP ports (including V380 variants)
                for port in [8080, 80, 8000, 8899, 554]:
                    try:
                        device = self._probe_device(ip, port, "", "", timeout)
                        if device:
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
    
    def _probe_device(self, ip: str, port: int, username: str, password: str, timeout: float) -> Optional[ONVIFDevice]:
        """Probe a single IP address for ONVIF service."""
        try:
            device = ONVIFDevice(ip, port, username, password)

            camera = self._create_camera(ip, port, username, password)
            
            # Get device info
            try:
                device_info = camera.devicemgmt.GetDeviceInformation()
                device.manufacturer = device_info.Manufacturer
                device.model = device_info.Model
                device.firmware_version = device_info.FirmwareVersion
            except Exception as e:
                logger.debug(f"Could not get device info for {ip}: {e}")
            
            # Get device hostname
            try:
                hostname_info = camera.devicemgmt.GetHostname()
                device.hostname = hostname_info.Hostname
            except Exception as e:
                logger.debug(f"Could not get hostname for {ip}: {e}")
            
            # Get stream URI
            try:
                stream_uri = self._get_stream_uri(camera)
                if stream_uri:
                    device.stream_uri = stream_uri
                    device.connected = True
                    return device
            except Exception as e:
                logger.debug(f"Could not get stream URI for {ip}: {e}")
        
        except Exception as e:
            logger.debug(f"Failed to probe {ip}:{port} - {e}")
        
        return None
    
    @staticmethod
    def _get_stream_uri(camera) -> Optional[str]:
        """Get RTSP stream URI from camera."""
        try:
            media_service = camera.create_media_service()
            profiles = media_service.GetProfiles()

            if not profiles:
                return None

            profile = profiles[0]

            request = media_service.create_type("GetStreamUri")
            request.ProfileToken = profile.token
            request.StreamSetup = {
                "Stream": "RTP-Unicast",
                "Transport": {"Protocol": "RTSP"},
            }
            stream_info = media_service.GetStreamUri(request)

            return stream_info.Uri

        except Exception as e:
            logger.error(f"Error getting stream URI: {e}")
            return None
    
    def add_device_manual(self, ip: str, port: int = 8080, username: str = "", password: str = "") -> Optional[ONVIFDevice]:
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
            logger.error("ONVIF not available")
            return None

        try:
            candidate_ports = []
            for candidate_port in [port, 80, 8080, 8000, 8899, 554]:
                if candidate_port not in candidate_ports:
                    candidate_ports.append(candidate_port)

            for candidate_port in candidate_ports:
                device = self._probe_device(ip, candidate_port, username, password, timeout=5)
                if not device:
                    continue

                for existing in list(self.devices):
                    if existing.ip == device.ip:
                        self.devices.remove(existing)
                        break
                self.devices.append(device)
                return device

            return None
        except Exception as e:
            logger.error(f"Failed to add device {ip}: {e}")
            return None
    
    def stop_discovery(self):
        """Stop any ongoing discovery."""
        self.discovering = False
    
    def get_device_stream(self, device: ONVIFDevice) -> Optional[str]:
        """Get the stream URI for a device."""
        if device.stream_uri:
            return device.stream_uri
        
        # Try to retrieve if not cached
        try:
            if ONVIF_AVAILABLE:
                camera = self._create_camera(
                    device.ip,
                    device.port,
                    device.username,
                    device.password,
                )
                stream_uri = self._get_stream_uri(camera)
                if stream_uri:
                    device.stream_uri = stream_uri
                    return stream_uri
        except Exception as e:
            logger.error(f"Failed to get stream for {device}: {e}")
        
        return None
