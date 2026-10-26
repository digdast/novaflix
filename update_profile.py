import sys
import urllib.request
import json
import base64
import ctypes
from ctypes import wintypes

sys.stdout.reconfigure(encoding='utf-8')

class CREDENTIAL_ATTRIBUTE(ctypes.Structure):
    _fields_ = [
        ('Keyword', wintypes.LPWSTR),
        ('Flags', wintypes.DWORD),
        ('ValueSize', wintypes.DWORD),
        ('Value', ctypes.POINTER(ctypes.c_byte))
    ]

class CREDENTIAL(ctypes.Structure):
    _fields_ = [
        ('Flags', wintypes.DWORD),
        ('Type', wintypes.DWORD),
        ('TargetName', wintypes.LPWSTR),
        ('Comment', wintypes.LPWSTR),
        ('LastWritten', wintypes.FILETIME),
        ('CredentialBlobSize', wintypes.DWORD),
        ('CredentialBlob', ctypes.POINTER(ctypes.c_byte)),
        ('Persist', wintypes.DWORD),
        ('AttributeCount', wintypes.DWORD),
        ('Attributes', ctypes.POINTER(CREDENTIAL_ATTRIBUTE)),
        ('TargetAlias', wintypes.LPWSTR),
        ('UserName', wintypes.LPWSTR)
    ]

PCREDENTIAL = ctypes.POINTER(CREDENTIAL)
advapi32 = ctypes.windll.advapi32
CredRead = advapi32.CredReadW
CredRead.argtypes = [wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(PCREDENTIAL)]
CredRead.restype = wintypes.BOOL
CredFree = advapi32.CredFree
CredFree.argtypes = [ctypes.c_void_p]

p_cred = PCREDENTIAL()
target = 'LegacyGeneric:target=GitHub - https://api.github.com/digdast'
if not CredRead(target, 1, 0, ctypes.byref(p_cred)):
    raise Exception('CredRead failed')

token = ctypes.string_at(p_cred.contents.CredentialBlob, p_cred.contents.CredentialBlobSize).decode('utf-8')
CredFree(p_cred)

HEADERS = {
    'Authorization': f'token {token}',
    'Accept': 'application/vnd.github.v3+json',
    'User-Agent': 'Python-Antigravity'
}

profile_readme = """<div align="center">

# ⚡ Efrain Rivas (`@digdast`)

<a href="https://github.com/digdast">
  <img src="https://readme-typing-svg.demolab.com?font=Fira+Code&weight=600&size=24&pause=1000&color=38BDF8&center=true&vCenter=true&width=650&lines=Hi%2C+I'm+Efrain+Rivas+(%40digdast)+%F0%9F%91%8B;Creator+of+NovaFlix+-+Sovereign+Media+Server;Creator+of+AegisDNS+-+Recursive+DoH+Sinkhole;Creator+of+Pulsearr+-+Next-Gen+Media+PVR;Cloud+%26+Infrastructure+Systems+Engineer" alt="Typing SVG" />
</a>

<p align="center">
  <img src="https://img.shields.io/badge/Location-Cary%2C%20NC-blue?style=for-the-badge&logo=google-maps&logoColor=white" />
  <img src="https://img.shields.io/badge/Flagship-NovaFlix%20Media-8b5cf6?style=for-the-badge&logo=media&logoColor=white" />
  <img src="https://img.shields.io/badge/Flagship-AegisDNS-06b6d4?style=for-the-badge&logo=dns&logoColor=white" />
  <img src="https://img.shields.io/badge/Flagship-Pulsearr-f59e0b?style=for-the-badge&logo=python&logoColor=white" />
</p>

</div>

---

### 👨‍💻 About Me

I am a **Senior Cloud & Systems Engineer** specializing in enterprise endpoint management, identity governance, cyber threat defense, and sovereign self-hosted infrastructure. My work focuses on building robust, high-performance open-source tools across media orchestration, network security, and modern cloud architectures.

- 🎬 **Creator of [NovaFlix](https://github.com/digdast/novaflix)**: The sovereign open-source media platform combining the best of Plex, Jellyfin, and Emby with zero ads, free 4K Direct Play, built-in remote access, SyncPlay, and cross-platform downloads.
- 🛡️ **Creator of [AegisDNS](https://github.com/digdast/aegisdns)**: Next-gen recursive DNS resolver, RFC 8484 DNS-over-HTTPS (DoH), and threat defense engine with an executive cyber command center.
- 🚀 **Creator of [Pulsearr](https://github.com/digdast/pulsearr)**: Asynchronous Python media PVR unifying Sonarr, Radarr, and Prowlarr into a single ultra-fast daemon.
- 🎬 **Creator of [Renamarr](https://github.com/digdast/renamarr)**: High-velocity IMDb-powered media organizer with remote CLI agent, cross-platform UI, and recursive SMB/NFS renaming.
- 📦 **[Proxmox Cluster Suite](https://github.com/digdast/proxmox-cluster-suite)**: Automated multi-node hypervisor tuning, K3s on LXC orchestration, and real-time telemetry dashboard.

---

### 🌟 Featured Flagship Projects

<table align="center" width="100%">
  <tr>
    <td width="50%" valign="top">
      <h3 align="center"><a href="https://github.com/digdast/novaflix">🎬 NovaFlix</a></h3>
      <p align="center">
        <img src="https://img.shields.io/badge/Streaming-HTTP%20206%20Direct%20Play-8b5cf6?style=flat-square" />
        <img src="https://img.shields.io/badge/SyncPlay-Watch%20Together-brightgreen?style=flat-square" />
        <img src="https://img.shields.io/badge/Remote%20Access-Zero--Conf-blue?style=flat-square" />
      </p>
      <p>Sovereign Open-Source Media Platform combining the elegance of Plex, freedom of Jellyfin, and power of Emby. 4K HDR Direct Play, SyncPlay watch together with live chat, multi-user profiles, and Plex-style download portal for Windows, macOS, Linux, and Docker.</p>
    </td>
    <td width="50%" valign="top">
      <h3 align="center"><a href="https://github.com/digdast/aegisdns">🛡️ AegisDNS</a></h3>
      <p align="center">
        <img src="https://img.shields.io/badge/DNS-RFC%208484%20DoH-06b6d4?style=flat-square" />
        <img src="https://img.shields.io/badge/Recursion-Root%20Hints-brightgreen?style=flat-square" />
        <img src="https://img.shields.io/badge/Blocklists-220k%2B%20Rules-red?style=flat-square" />
      </p>
      <p>Next-Gen Recursive DNS Sinkhole & DoH Resolver. Features pure root iterative recursion, active malware/ad sinkholing, SafeSearch enforcement, homelab local DNS records, and an executive glassmorphic cyber command center.</p>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <h3 align="center"><a href="https://github.com/digdast/pulsearr">⚡ Pulsearr</a></h3>
      <p align="center">
        <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white" />
        <img src="https://img.shields.io/badge/FastAPI-Async-009688?style=flat-square&logo=fastapi&logoColor=white" />
        <img src="https://img.shields.io/badge/Status-Active-brightgreen?style=flat-square" />
      </p>
      <p>Unified Asynchronous Media PVR combining <b>Sonarr (TV)</b>, <b>Radarr (Movies)</b>, and <b>Prowlarr (Trackers Hub)</b> into a unified ultra-fast daemon with async SQLite WAL mode and remote qBittorrent integration.</p>
    </td>
    <td width="50%" valign="top">
      <h3 align="center"><a href="https://github.com/digdast/renamarr">🎬 Renamarr</a></h3>
      <p align="center">
        <img src="https://img.shields.io/badge/IMDb-Automated-yellow?style=flat-square" />
        <img src="https://img.shields.io/badge/CLI-Remote%20Host-blue?style=flat-square" />
      </p>
      <p>Interactive IMDb & TV media organizer with recursive directory inspection, custom pattern tokenization, interactive diff preview, and remote execution across NAS, SMB, and NFS storage.</p>
    </td>
  </tr>
</table>

---

### 🛠️ Tech Stack & Engineering Toolkit

<div align="center">

#### Cloud, Systems & Media Orchestration
<img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white" />
<img src="https://img.shields.io/badge/PowerShell-5391FE?style=for-the-badge&logo=powershell&logoColor=white" />
<img src="https://img.shields.io/badge/Bash-4EAA25?style=for-the-badge&logo=gnu-bash&logoColor=white" />
<img src="https://img.shields.io/badge/Kubernetes-326CE5?style=for-the-badge&logo=kubernetes&logoColor=white" />
<img src="https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white" />
<img src="https://img.shields.io/badge/Proxmox%20VE-E57000?style=for-the-badge&logo=proxmox&logoColor=white" />
<img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" />
<img src="https://img.shields.io/badge/SQLite%20WAL-003B57?style=for-the-badge&logo=sqlite&logoColor=white" />

</div>
"""

url = "https://api.github.com/repos/digdast/digdast/contents/README.md"
sha = None
try:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        sha = data.get('sha')
except Exception as e:
    pass

b64 = base64.b64encode(profile_readme.encode('utf-8')).decode('utf-8')
payload = {
    'message': 'docs: Showcase NovaFlix as flagship sovereign media platform in profile',
    'content': b64,
    'branch': 'main'
}
if sha:
    payload['sha'] = sha

req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=HEADERS, method='PUT')
with urllib.request.urlopen(req) as resp:
    print(f"Profile README updated successfully! HTTP {resp.status}")
