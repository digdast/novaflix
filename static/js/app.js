/**
 * NovaFlix - Cinema Web Client & Video Player Engine
 * Handles catalog browsing, HTTP 206 Direct Play streaming, resume playback,
 * SyncPlay (Watch Together) synchronization, and remote access testing.
 */

class NovaFlixApp {
    constructor() {
        this.currentMedia = null;
        this.currentUser = { id: 1, username: 'Admin', is_admin: true };
        this.syncSocket = null;
        this.syncRoomId = null;
        this.progressTimer = null;

        this.initElements();
        this.initEventListeners();
        this.loadCatalog();
    }

    initElements() {
        this.video = document.getElementById('mainVideoElement');
        this.playerModal = document.getElementById('videoPlayerModal');
        this.playPauseBtn = document.getElementById('btnPlayPause');
        this.scrubberBar = document.getElementById('playerScrubberBar');
        this.scrubberFill = document.getElementById('playerScrubberFill');
        this.timeDisplay = document.getElementById('playerTimeDisplay');
        this.volumeSlider = document.getElementById('playerVolumeSlider');
    }

    initEventListeners() {
        // Video element events
        if (this.video) {
            this.video.addEventListener('timeupdate', () => this.onTimeUpdate());
            this.video.addEventListener('ended', () => this.onEnded());
            this.video.addEventListener('play', () => this.updatePlayIcon(true));
            this.video.addEventListener('pause', () => this.updatePlayIcon(false));
        }

        // Scrubber seeking
        if (this.scrubberBar) {
            this.scrubberBar.addEventListener('click', (e) => {
                if (!this.video || !this.video.duration) return;
                const rect = this.scrubberBar.getBoundingClientRect();
                const pos = (e.clientX - rect.left) / rect.width;
                this.video.currentTime = pos * this.video.duration;
                if (this.syncSocket && this.syncRoomId) {
                    this.sendSyncMessage({ type: 'SEEK', position: this.video.currentTime });
                }
            });
        }

        // Keyboard Shortcuts
        window.addEventListener('keydown', (e) => {
            if (!this.playerModal || !this.playerModal.classList.contains('active')) return;
            if (e.code === 'Space') {
                e.preventDefault();
                this.togglePlay();
            } else if (e.code === 'KeyF') {
                e.preventDefault();
                this.toggleFullscreen();
            } else if (e.code === 'KeyM') {
                e.preventDefault();
                this.toggleMute();
            } else if (e.code === 'ArrowRight') {
                this.video.currentTime += 10;
            } else if (e.code === 'ArrowLeft') {
                this.video.currentTime -= 10;
            } else if (e.code === 'Escape') {
                this.closePlayer();
            }
        });

        // Search Input
        const searchInput = document.getElementById('navSearchInput');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                const term = e.target.value.toLowerCase().trim();
                this.filterMedia(term);
            });
        }

        // Remote Access Modal Trigger
        const btnRemote = document.getElementById('btnRemoteStatus');
        if (btnRemote) {
            btnRemote.addEventListener('click', () => this.openRemoteModal());
        }

        // Add Media & Library Nav Triggers
        const btnAddMedia = document.getElementById('btnNavAddMedia');
        if (btnAddMedia) {
            btnAddMedia.addEventListener('click', () => this.openAddMediaModal('single'));
        }
        const btnLibraries = document.getElementById('btnNavLibraries');
        if (btnLibraries) {
            btnLibraries.addEventListener('click', () => this.openAddMediaModal('scan'));
        }
    }

    // -------------------------------------------------------------
    // Catalog Loading & Rendering
    // -------------------------------------------------------------

    async loadCatalog() {
        try {
            const [featuredRes, moviesRes, showsRes, continueRes] = await Promise.all([
                fetch('/api/media/featured').then(r => r.json()),
                fetch('/api/media/movies').then(r => r.json()),
                fetch('/api/media/shows').then(r => r.json()),
                fetch('/api/media/continue?user_id=' + this.currentUser.id).then(r => r.json())
            ]);

            this.renderFeatured(featuredRes);
            this.renderContinueWatching(continueRes);
            this.renderMovies(moviesRes);
            this.renderShows(showsRes);
        } catch (e) {
            console.error('Failed to load catalog', e);
        }
    }

    renderFeatured(item) {
        if (!item || !item.id) return;
        const heroBackdrop = document.getElementById('heroBackdrop');
        const heroTitle = document.getElementById('heroTitle');
        const heroSynopsis = document.getElementById('heroSynopsis');
        const heroRating = document.getElementById('heroRating');
        const heroYear = document.getElementById('heroYear');
        const heroDuration = document.getElementById('heroDuration');
        const heroGenre = document.getElementById('heroGenre');
        const btnPlay = document.getElementById('btnHeroPlay');

        if (heroBackdrop) heroBackdrop.style.backgroundImage = `url('${item.backdrop || item.poster}')`;
        if (heroTitle) heroTitle.innerText = item.title;
        if (heroSynopsis) heroSynopsis.innerText = item.synopsis || '';
        if (heroRating) heroRating.innerText = `★ ${item.rating || 9.0}`;
        if (heroYear) heroYear.innerText = item.year || 2026;
        if (heroDuration) heroDuration.innerText = item.duration || '2h';
        if (heroGenre) heroGenre.innerText = item.genre || 'Sci-Fi';

        if (btnPlay) {
            btnPlay.onclick = () => this.playMedia(item);
        }
    }

    renderContinueWatching(items) {
        const shelf = document.getElementById('shelfContinueWatching');
        const container = document.getElementById('carouselContinueWatching');
        if (!shelf || !container) return;

        if (!items || items.length === 0) {
            shelf.style.display = 'none';
            return;
        }

        shelf.style.display = 'block';
        container.innerHTML = items.map(m => {
            const percent = Math.min(100, Math.round((m.position_seconds / max(1, m.total_seconds)) * 100));
            return `
                <div class="media-card" onclick="app.playMediaById(${m.id})">
                    <div class="media-poster-wrap">
                        <img src="${m.backdrop || m.poster}" class="media-poster-img" alt="${m.title}">
                        <div class="media-overlay-play">
                            <div class="play-circle-btn">
                                <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
                            </div>
                        </div>
                        <div class="progress-bar-wrap">
                            <div class="progress-bar-fill" style="width: ${percent}%;"></div>
                        </div>
                    </div>
                    <div class="media-card-info">
                        <div class="media-card-title">${m.title}</div>
                        <div class="media-card-sub">
                            <span>Resume</span>
                            <span>${Math.round(m.position_seconds / 60)}m left</span>
                        </div>
                    </div>
                </div>
            `;
        }).join('');
    }

    renderMovies(movies) {
        const container = document.getElementById('carouselMovies');
        if (!container) return;
        container.innerHTML = movies.map(m => this.createMediaCard(m)).join('');
    }

    renderShows(shows) {
        const container = document.getElementById('carouselShows');
        if (!container) return;
        container.innerHTML = shows.map(s => this.createMediaCard(s)).join('');
    }

    createMediaCard(m) {
        return `
            <div class="media-card" onclick="app.openDetailModal(${m.id})">
                <div class="media-poster-wrap">
                    <img src="${m.poster}" class="media-poster-img" alt="${m.title}" loading="lazy">
                    <div class="media-overlay-play">
                        <div class="play-circle-btn">
                            <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
                        </div>
                    </div>
                </div>
                <div class="media-card-info">
                    <div class="media-card-title">${m.title}</div>
                    <div class="media-card-sub">
                        <span>${m.year || 2025}</span>
                        <span style="color: var(--amber-gold); font-weight: 700;">★ ${m.rating || 8.5}</span>
                    </div>
                </div>
            </div>
        `;
    }

    filterMedia(term) {
        document.querySelectorAll('.media-card').forEach(card => {
            const title = card.querySelector('.media-card-title')?.innerText.toLowerCase() || '';
            card.style.display = title.includes(term) ? 'block' : 'none';
        });
    }

    // -------------------------------------------------------------
    // Detail Modal & Playback Initiation
    // -------------------------------------------------------------

    async openDetailModal(itemId) {
        try {
            const res = await fetch(`/api/media/item/${itemId}`);
            const item = await res.json();
            this.currentMedia = item;

            const modal = document.getElementById('mediaDetailModal');
            const backdrop = document.getElementById('detailBackdrop');
            const title = document.getElementById('detailTitle');
            const synopsis = document.getElementById('detailSynopsis');
            const meta = document.getElementById('detailMeta');
            const cast = document.getElementById('detailCast');
            const btnPlay = document.getElementById('btnDetailPlay');
            const episodeList = document.getElementById('detailEpisodeList');

            if (backdrop) backdrop.style.backgroundImage = `url('${item.backdrop || item.poster}')`;
            if (title) title.innerText = item.title;
            if (synopsis) synopsis.innerText = item.synopsis || '';
            if (meta) meta.innerText = `${item.year || 2025} • ${item.duration || '2h'} • ${item.genre || 'Action'} • ${item.content_rating || 'PG-13'}`;
            if (cast) cast.innerText = item.cast ? `Starring: ${item.cast}` : '';

            if (btnPlay) {
                btnPlay.onclick = () => {
                    this.closeDetailModal();
                    if (item.type === 'show' && item.episodes && item.episodes.length > 0) {
                        this.playMedia(item.episodes[0]);
                    } else {
                        this.playMedia(item);
                    }
                };
            }

            // If it's a TV series, render episodes list
            if (episodeList) {
                if (item.type === 'show' && item.episodes && item.episodes.length > 0) {
                    episodeList.style.display = 'block';
                    episodeList.innerHTML = `
                        <h4 style="margin: 20px 0 12px; font-size: 1.1rem; color: #ffffff;">Episodes</h4>
                        ${item.episodes.map(ep => `
                            <div style="display: flex; justify-content: space-between; align-items: center; padding: 10px 14px; background: rgba(255,255,255,0.03); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); margin-bottom: 8px; cursor: pointer;" onclick="app.closeDetailModal(); app.playMediaById(${ep.id});">
                                <div>
                                    <span style="font-weight: 700; color: #ffffff;">S${ep.season_number} E${ep.episode_number}: ${ep.title}</span>
                                    <div style="font-size: 0.8rem; color: var(--text-muted);">${ep.duration || '45m'}</div>
                                </div>
                                <span class="play-circle-btn" style="width: 32px; height: 32px;"><svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg></span>
                            </div>
                        `).join('')}
                    `;
                } else {
                    episodeList.style.display = 'none';
                }
            }

            modal.classList.add('active');
        } catch (e) {
            console.error('Failed to open detail modal', e);
        }
    }

    closeDetailModal() {
        const modal = document.getElementById('mediaDetailModal');
        if (modal) modal.classList.remove('active');
    }

    async playMediaById(itemId) {
        try {
            const res = await fetch(`/api/media/item/${itemId}`);
            const item = await res.json();
            this.playMedia(item);
        } catch (e) {
            console.error('Failed to play item', e);
        }
    }

    playMedia(item) {
        this.currentMedia = item;
        const streamUrl = `/stream/${item.id}`;
        
        document.getElementById('playerItemTitle').innerText = item.title;
        this.video.src = streamUrl;
        this.playerModal.classList.add('active');
        this.video.play().catch(() => {});

        // Start background progress recording every 5 seconds
        clearInterval(this.progressTimer);
        this.progressTimer = setInterval(() => this.recordProgress(), 5000);
    }

    closePlayer() {
        if (this.video) {
            this.recordProgress();
            this.video.pause();
            this.video.src = '';
        }
        clearInterval(this.progressTimer);
        if (this.playerModal) this.playerModal.classList.remove('active');
        this.loadCatalog();
    }

    // -------------------------------------------------------------
    // Player Controls
    // -------------------------------------------------------------

    togglePlay() {
        if (!this.video) return;
        if (this.video.paused) {
            this.video.play();
            if (this.syncSocket && this.syncRoomId) {
                this.sendSyncMessage({ type: 'PLAY', position: this.video.currentTime });
            }
        } else {
            this.video.pause();
            if (this.syncSocket && this.syncRoomId) {
                this.sendSyncMessage({ type: 'PAUSE', position: this.video.currentTime });
            }
        }
    }

    updatePlayIcon(isPlaying) {
        const icon = document.getElementById('iconPlayPause');
        if (!icon) return;
        icon.innerHTML = isPlaying
            ? '<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="4" width="4" height="16"></rect><rect x="14" y="4" width="4" height="16"></rect></svg>'
            : '<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>';
    }

    onTimeUpdate() {
        if (!this.video || !this.video.duration) return;
        const current = this.video.currentTime;
        const total = this.video.duration;
        const percent = (current / total) * 100;

        if (this.scrubberFill) this.scrubberFill.style.width = `${percent}%`;
        if (this.timeDisplay) {
            this.timeDisplay.innerText = `${this.formatTime(current)} / ${this.formatTime(total)}`;
        }
    }

    onEnded() {
        this.recordProgress(true);
        this.closePlayer();
    }

    formatTime(sec) {
        const m = Math.floor(sec / 60);
        const s = Math.floor(sec % 60);
        return `${m}:${s < 10 ? '0' : ''}${s}`;
    }

    toggleFullscreen() {
        if (!document.fullscreenElement) {
            this.playerModal.requestFullscreen().catch(() => {});
        } else {
            document.exitFullscreen().catch(() => {});
        }
    }

    toggleMute() {
        if (!this.video) return;
        this.video.muted = !this.video.muted;
    }

    setVolume(val) {
        if (this.video) this.video.volume = parseFloat(val);
    }

    async recordProgress(completed = false) {
        if (!this.currentMedia || !this.video || !this.video.duration) return;
        try {
            await fetch('/api/media/progress', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    user_id: this.currentUser.id,
                    media_id: this.currentMedia.id,
                    position_seconds: completed ? this.video.duration : this.video.currentTime,
                    duration_seconds: this.video.duration
                })
            });
        } catch (e) {}
    }

    // -------------------------------------------------------------
    // SyncPlay (Watch Together) Integration
    // -------------------------------------------------------------

    toggleSyncPlayPanel() {
        const sidebar = document.getElementById('syncPlaySidebar');
        if (!sidebar) return;
        sidebar.classList.toggle('active');

        if (sidebar.classList.contains('active') && !this.syncSocket) {
            this.initSyncPlayRoom('DEMO-ROOM-1');
        }
    }

    initSyncPlayRoom(roomId) {
        this.syncRoomId = roomId;
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const url = `${protocol}//${window.location.host}/ws/syncplay/${roomId}`;

        try {
            this.syncSocket = new WebSocket(url);

            this.syncSocket.onmessage = (event) => {
                const data = JSON.parse(event.data);
                this.handleSyncMessage(data);
            };

            this.syncSocket.onclose = () => {
                this.syncSocket = null;
            };
        } catch (e) {
            console.error('SyncPlay socket error', e);
        }
    }

    sendSyncMessage(msg) {
        if (this.syncSocket && this.syncSocket.readyState === WebSocket.OPEN) {
            this.syncSocket.send(JSON.stringify(msg));
        }
    }

    handleSyncMessage(data) {
        if (data.type === 'PLAY') {
            if (this.video && this.video.paused) {
                this.video.currentTime = data.position;
                this.video.play().catch(() => {});
            }
        } else if (data.type === 'PAUSE') {
            if (this.video && !this.video.paused) {
                this.video.currentTime = data.position;
                this.video.pause();
            }
        } else if (data.type === 'SEEK') {
            if (this.video) {
                this.video.currentTime = data.position;
            }
        } else if (data.type === 'CHAT') {
            const container = document.getElementById('syncChatMessages');
            if (container) {
                container.innerHTML += `
                    <div class="chat-bubble">
                        <div class="chat-author">${data.username}</div>
                        <div>${data.text}</div>
                    </div>
                `;
                container.scrollTop = container.scrollHeight;
            }
        }
    }

    sendChatMessage() {
        const input = document.getElementById('syncChatInput');
        if (!input || !input.value.trim()) return;
        this.sendSyncMessage({
            type: 'CHAT',
            username: this.currentUser.username,
            text: input.value.trim()
        });
        input.value = '';
    }

    // -------------------------------------------------------------
    // Remote Access Modal
    // -------------------------------------------------------------

    async openRemoteModal() {
        const modal = document.getElementById('remoteAccessModal');
        if (!modal) return;
        modal.classList.add('active');

        try {
            const res = await fetch('/api/system/remote');
            const info = await res.json();
            document.getElementById('remoteWanIp').innerText = info.public_ip;
            document.getElementById('remoteLanIp').innerText = info.lan_ip;
            document.getElementById('remotePort').innerText = info.port;
            document.getElementById('remotePublicUrl').innerText = info.remote_url;
            document.getElementById('remoteLocalUrl').innerText = info.local_url;
        } catch (e) {}
    }

    closeRemoteModal() {
        const modal = document.getElementById('remoteAccessModal');
        if (modal) modal.classList.remove('active');
    }

    // -------------------------------------------------------------
    // Add Media & Library Management
    // -------------------------------------------------------------

    openAddMediaModal(tab = 'single') {
        const modal = document.getElementById('addMediaModal');
        if (!modal) return;
        modal.classList.add('active');
        this.switchAddMediaTab(tab);
        this.loadLibraries();
    }

    closeAddMediaModal() {
        const modal = document.getElementById('addMediaModal');
        if (modal) modal.classList.remove('active');
    }

    switchAddMediaTab(tab) {
        const tabSingle = document.getElementById('tabBtnAddSingle');
        const tabScan = document.getElementById('tabBtnScanStorage');
        const contentSingle = document.getElementById('tabContentAddSingle');
        const contentScan = document.getElementById('tabContentScanStorage');

        if (tab === 'single') {
            if (tabSingle) tabSingle.classList.add('active');
            if (tabScan) tabScan.classList.remove('active');
            if (contentSingle) contentSingle.classList.add('active');
            if (contentScan) contentScan.classList.remove('active');
        } else {
            if (tabSingle) tabSingle.classList.remove('active');
            if (tabScan) tabScan.classList.add('active');
            if (contentSingle) contentSingle.classList.remove('active');
            if (contentScan) contentScan.classList.add('active');
            this.loadLibraries();
        }
    }

    onMediaTypeChange() {
        const type = document.getElementById('addMediaType')?.value || 'movie';
        const libSelect = document.getElementById('addMediaLibrarySelect');
        if (!libSelect) return;
        for (let opt of libSelect.options) {
            const optType = opt.getAttribute('data-type');
            if ((type === 'movie' && optType === 'movies') || (type === 'show' && optType === 'tvshows')) {
                libSelect.value = opt.value;
                break;
            }
        }
    }

    generatePosterPreview() {
        const title = document.getElementById('addMediaTitle')?.value.trim();
        const year = document.getElementById('addMediaYear')?.value.trim() || '';
        const genre = document.getElementById('addMediaGenre')?.value.trim() || 'Cinema';
        if (!title) {
            this.showToast('Please enter a title first', 'error');
            return;
        }
        const genUrl = `/api/media/poster/generated?title=${encodeURIComponent(title)}&year=${encodeURIComponent(year)}&genre=${encodeURIComponent(genre)}`;
        const posterInput = document.getElementById('addMediaPoster');
        if (posterInput) posterInput.value = genUrl;
        this.showToast('Generated dynamic cinema poster!', 'info');
    }

    async submitAddMedia() {
        const title = document.getElementById('addMediaTitle')?.value.trim();
        const type = document.getElementById('addMediaType')?.value || 'movie';
        const year = parseInt(document.getElementById('addMediaYear')?.value) || 2026;
        const rating = parseFloat(document.getElementById('addMediaRating')?.value) || 8.5;
        const genre = document.getElementById('addMediaGenre')?.value.trim() || 'Cinema';
        const filePath = document.getElementById('addMediaFilePath')?.value.trim() || '';
        const streamUrl = document.getElementById('addMediaStreamUrl')?.value.trim() || '';
        const poster = document.getElementById('addMediaPoster')?.value.trim() || '';
        const synopsis = document.getElementById('addMediaSynopsis')?.value.trim() || '';
        const libSelect = document.getElementById('addMediaLibrarySelect');
        const libraryId = libSelect ? parseInt(libSelect.value) : 1;

        if (!title) {
            this.showToast('Title is required', 'error');
            return;
        }
        if (!filePath && !streamUrl) {
            this.showToast('Provide either a local file path or stream URL', 'error');
            return;
        }

        const btn = document.getElementById('btnSubmitAddMedia');
        if (btn) btn.disabled = true;

        try {
            const res = await fetch('/api/media/add', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    title,
                    type,
                    year,
                    rating,
                    genre,
                    file_path: filePath,
                    stream_url: streamUrl,
                    poster,
                    synopsis,
                    library_id: libraryId
                })
            });

            const data = await res.json();
            if (res.ok) {
                this.showToast(`✨ Added "${title}" to your library!`, 'success');
                this.closeAddMediaModal();
                document.getElementById('formAddMedia')?.reset();
                await this.loadCatalog();
            } else {
                this.showToast(data.detail || 'Failed to add media item', 'error');
            }
        } catch (e) {
            this.showToast(`Error: ${e.message}`, 'error');
        } finally {
            if (btn) btn.disabled = false;
        }
    }

    async deleteCurrentMedia() {
        if (!this.currentMedia || !this.currentMedia.id) return;
        const confirmDelete = confirm(`Are you sure you want to remove "${this.currentMedia.title}" from NovaFlix?`);
        if (!confirmDelete) return;

        try {
            const res = await fetch(`/api/media/item/${this.currentMedia.id}`, { method: 'DELETE' });
            if (res.ok) {
                this.showToast(`Removed "${this.currentMedia.title}" from library`, 'info');
                this.closeDetailModal();
                await this.loadCatalog();
            } else {
                this.showToast('Failed to delete media item', 'error');
            }
        } catch (e) {
            this.showToast(`Delete failed: ${e.message}`, 'error');
        }
    }

    async loadLibraries() {
        const container = document.getElementById('librariesListContainer');
        const libSelect = document.getElementById('addMediaLibrarySelect');

        try {
            const res = await fetch('/api/libraries');
            const libs = await res.json();

            if (libSelect) {
                libSelect.innerHTML = libs.map(l => `
                    <option value="${l.id}" data-type="${l.type}">${l.name} (${l.type})</option>
                `).join('');
            }

            if (container) {
                if (!libs || libs.length === 0) {
                    container.innerHTML = '<div style="color: var(--text-muted); padding: 12px;">No libraries configured yet. Add one below.</div>';
                    return;
                }

                container.innerHTML = libs.map(l => `
                    <div class="library-card-item">
                        <div>
                            <div style="display: flex; align-items: center; gap: 8px;">
                                <span style="font-weight: 700; color: #ffffff;">${l.name}</span>
                                <span class="rating-badge" style="font-size: 0.7rem;">${l.type.toUpperCase()}</span>
                                <span style="font-size: 0.8rem; color: var(--amber-gold); font-family: var(--font-mono);">${l.item_count} items</span>
                            </div>
                            <div style="font-size: 0.8rem; font-family: var(--font-mono); color: var(--text-muted); margin-top: 4px;">${l.path}</div>
                        </div>
                        <div style="display: flex; gap: 8px;">
                            <button class="btn-tag" style="background: rgba(245, 158, 11, 0.15); color: var(--amber-gold); border-color: rgba(245, 158, 11, 0.3);" onclick="app.startLibraryScan(${l.id})">
                                ↻ Scan
                            </button>
                            <button class="btn-tag" style="background: rgba(244, 63, 94, 0.1); color: var(--rose-danger); border-color: rgba(244, 63, 94, 0.25);" onclick="app.deleteLibrary(${l.id}, '${l.name}')">
                                ✕
                            </button>
                        </div>
                    </div>
                `).join('');
            }
        } catch (e) {
            console.error('Failed to load libraries', e);
        }
    }

    async quickAddLibrary(name, type, path) {
        try {
            const res = await fetch('/api/libraries', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, type, path })
            });
            if (res.ok) {
                this.showToast(`Configured library: ${name}`, 'success');
                await this.loadLibraries();
                this.startLibraryScan();
            } else {
                const data = await res.json();
                this.showToast(data.detail || 'Could not add preset', 'error');
            }
        } catch (e) {
            this.showToast(`Error: ${e.message}`, 'error');
        }
    }

    async createLibrary() {
        const name = document.getElementById('newLibName')?.value.trim();
        const type = document.getElementById('newLibType')?.value || 'movies';
        const path = document.getElementById('newLibPath')?.value.trim();

        if (!name || !path) {
            this.showToast('Please provide both Library Name and Path', 'error');
            return;
        }

        try {
            const res = await fetch('/api/libraries', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, type, path })
            });
            if (res.ok) {
                this.showToast(`Added library "${name}"`, 'success');
                document.getElementById('newLibName').value = '';
                document.getElementById('newLibPath').value = '';
                await this.loadLibraries();
            } else {
                const data = await res.json();
                this.showToast(data.detail || 'Failed to create library', 'error');
            }
        } catch (e) {
            this.showToast(`Error: ${e.message}`, 'error');
        }
    }

    async deleteLibrary(libId, name) {
        if (!confirm(`Remove library "${name}"? Existing media records will remain.`)) return;
        try {
            const res = await fetch(`/api/libraries/${libId}`, { method: 'DELETE' });
            if (res.ok) {
                this.showToast(`Library "${name}" deleted`, 'info');
                await this.loadLibraries();
            }
        } catch (e) {
            this.showToast(`Error: ${e.message}`, 'error');
        }
    }

    async startLibraryScan(libId = null) {
        const card = document.getElementById('scanProgressCard');
        const badge = document.getElementById('scanStatusBadge');
        const stats = document.getElementById('scanStatsDisplay');
        const btn = document.getElementById('btnScanAllLibraries');

        if (card) card.style.display = 'block';
        if (badge) { badge.innerText = 'SCANNING'; badge.style.color = 'var(--amber-gold)'; }
        if (btn) btn.disabled = true;

        this.showToast('🚀 Scanning media directories...', 'info');

        try {
            const res = await fetch('/api/libraries/scan', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ library_id: libId })
            });

            const data = await res.json();
            let totalAdded = 0;
            let totalScanned = 0;

            if (data.results) {
                data.results.forEach(r => {
                    totalAdded += (r.added || 0);
                    totalScanned += (r.scanned || 0);
                });
            }

            if (stats) {
                stats.innerText = `Scan Complete: Scanned ${totalScanned} files • Discovered ${totalAdded} new items`;
            }

            this.showToast(`🎉 Scan complete! Added ${totalAdded} new items.`, 'success');
            await this.loadCatalog();
            await this.loadLibraries();
        } catch (e) {
            this.showToast(`Scan error: ${e.message}`, 'error');
        } finally {
            if (badge) { badge.innerText = 'IDLE'; badge.style.color = '#ffffff'; }
            if (btn) btn.disabled = false;
            setTimeout(() => {
                if (card) card.style.display = 'none';
            }, 4000);
        }
    }

    // -------------------------------------------------------------
    // Filesystem Directory Browser
    // -------------------------------------------------------------

    openFolderBrowser(targetInputId) {
        this.targetBrowserInputId = targetInputId;
        const modal = document.getElementById('folderBrowserModal');
        if (modal) modal.classList.add('active');
        const initialVal = document.getElementById(targetInputId)?.value.trim();
        this.browsePath(initialVal || '/data/media');
    }

    closeFolderBrowser() {
        const modal = document.getElementById('folderBrowserModal');
        if (modal) modal.classList.remove('active');
    }

    async browsePath(path) {
        const list = document.getElementById('browserEntriesList');
        const currentPathEl = document.getElementById('browserCurrentPath');
        const btnParent = document.getElementById('btnBrowserParent');

        if (list) list.innerHTML = '<div style="color: var(--text-muted); padding: 8px;">Loading server directory...</div>';

        try {
            const res = await fetch(`/api/filesystem/browse?path=${encodeURIComponent(path || '')}`);
            const data = await res.json();

            this.currentBrowserPath = data.current_path;
            this.currentBrowserParent = data.parent_path;

            if (currentPathEl) currentPathEl.innerText = data.current_path;
            if (btnParent) btnParent.disabled = !data.parent_path;

            if (list) {
                let html = '';
                if (data.suggested_paths && data.suggested_paths.length > 0 && (!path || path === '/data/media' || path === '/data')) {
                    html += `<div style="font-size: 0.75rem; color: var(--amber-gold); font-weight: 700; margin-bottom: 4px;">FAST SHORTCUTS:</div>`;
                    data.suggested_paths.forEach(s => {
                        html += `
                            <div class="browser-entry-item is-dir" onclick="app.browsePath('${s.path}')">
                                <span>⭐ ${s.name}</span>
                                <span style="font-size: 0.75rem; color: var(--text-muted);">${s.type}</span>
                            </div>
                        `;
                    });
                    html += `<div style="height: 8px;"></div>`;
                }

                data.directories.forEach(d => {
                    const subPath = data.current_path.replace(/\/$/, '') + '/' + d;
                    html += `
                        <div class="browser-entry-item is-dir" onclick="app.browsePath('${subPath.replace(/'/g, "\\'")}')">
                            <span>📁 ${d}</span>
                            <span style="font-size: 0.75rem; color: var(--text-muted);">folder</span>
                        </div>
                    `;
                });

                data.video_files.forEach(f => {
                    const filePath = data.current_path.replace(/\/$/, '') + '/' + f;
                    html += `
                        <div class="browser-entry-item is-file" onclick="app.selectBrowserItem('${filePath.replace(/'/g, "\\'")}')">
                            <span>🎬 ${f}</span>
                            <span style="font-size: 0.75rem; color: var(--cyan-accent);">select</span>
                        </div>
                    `;
                });

                if (data.directories.length === 0 && data.video_files.length === 0) {
                    html += '<div style="color: var(--text-muted); padding: 8px;">(Folder is empty)</div>';
                }

                list.innerHTML = html;
            }
        } catch (e) {
            if (list) list.innerHTML = `<div style="color: var(--rose-danger); padding: 8px;">Failed to browse: ${e.message}</div>`;
        }
    }

    browseParentDir() {
        if (this.currentBrowserParent) {
            this.browsePath(this.currentBrowserParent);
        }
    }

    selectCurrentBrowserPath() {
        if (this.targetBrowserInputId && this.currentBrowserPath) {
            const input = document.getElementById(this.targetBrowserInputId);
            if (input) input.value = this.currentBrowserPath;
        }
        this.closeFolderBrowser();
    }

    selectBrowserItem(itemPath) {
        if (this.targetBrowserInputId) {
            const input = document.getElementById(this.targetBrowserInputId);
            if (input) input.value = itemPath;
        }
        this.closeFolderBrowser();
    }

    // -------------------------------------------------------------
    // Toast Notification System
    // -------------------------------------------------------------

    showToast(message, type = 'info', duration = 3500) {
        const container = document.getElementById('toastContainer');
        if (!container) return;

        const toast = document.createElement('div');
        toast.className = `toast-message toast-${type}`;
        
        let icon = 'ℹ️';
        if (type === 'success') icon = '✓';
        if (type === 'error') icon = '✕';

        toast.innerHTML = `
            <span style="font-weight: 800; font-size: 1rem;">${icon}</span>
            <span>${message}</span>
        `;

        container.appendChild(toast);

        setTimeout(() => {
            toast.style.opacity = '0';
            setTimeout(() => toast.remove(), 300);
        }, duration);
    }
}

// Global App Instance
window.app = new NovaFlixApp();
