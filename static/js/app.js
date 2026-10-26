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
        this.libraries = [];
        this.currentLibraryFilter = null;
        this.showsList = [];

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
            this.video.addEventListener('error', () => {
                console.error('Video error encountered:', this.video.error);
                if (this.currentMedia && !this.video.src.includes('transcode=1')) {
                    this.showToast('Adapting stream for browser compatibility...', 'info');
                    this.video.src = `/stream/${this.currentMedia.id}?transcode=1`;
                    this.video.play().catch(() => {});
                } else {
                    this.showToast('Playback error: Unable to decode stream.', 'error');
                }
            });
        }

        // Scrubber seeking
        if (this.scrubberBar) {
            this.scrubberBar.addEventListener('click', (e) => {
                if (!this.video) return;
                const totalDuration = (this.currentMedia && this.currentMedia.duration_seconds) ? this.currentMedia.duration_seconds : this.video.duration;
                if (!totalDuration) return;

                const rect = this.scrubberBar.getBoundingClientRect();
                const pos = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
                const targetTime = pos * totalDuration;

                if (!this.video.duration || !isFinite(this.video.duration)) {
                    this.seekOffset = targetTime;
                    this.video.src = `/stream/${this.currentMedia.id}?start=${Math.floor(targetTime)}`;
                    this.video.play().catch(() => {});
                } else {
                    this.video.currentTime = targetTime;
                }

                if (this.syncSocket && this.syncRoomId) {
                    this.sendSyncMessage({ type: 'SEEK', position: targetTime });
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
                this.seekRelative(10);
            } else if (e.code === 'ArrowLeft') {
                this.seekRelative(-10);
            } else if (e.code === 'ArrowUp') {
                e.preventDefault();
                this.setVolume(Math.min(1.0, (this.video?.volume || 1.0) + 0.1));
            } else if (e.code === 'ArrowDown') {
                e.preventDefault();
                this.setVolume(Math.max(0.0, (this.video?.volume || 1.0) - 0.1));
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
            const [featuredRes, libsRes, continueRes, showsListRes] = await Promise.all([
                fetch('/api/media/featured').then(r => r.json()),
                fetch('/api/libraries').then(r => r.json()),
                fetch('/api/media/continue?user_id=' + this.currentUser.id).then(r => r.json()),
                fetch('/api/shows/list').then(r => r.json())
            ]);

            this.libraries = libsRes || [];
            this.showsList = showsListRes || [];

            this.renderFeatured(featuredRes);
            this.renderContinueWatching(continueRes);
            this.renderLibraryPills();
            await this.renderDynamicShelves();
        } catch (e) {
            console.error('Failed to load catalog', e);
        }
    }

    renderLibraryPills() {
        const container = document.getElementById('dynamicLibraryPills');
        const pillAll = document.getElementById('pillAllMedia');
        if (pillAll) {
            pillAll.className = `lib-pill ${this.currentLibraryFilter === null ? 'active' : ''}`;
        }
        if (!container) return;

        container.innerHTML = this.libraries.map(l => {
            const isMovie = l.type === 'movies';
            const iconSvg = isMovie
                ? '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="2" width="20" height="20" rx="2.18" ry="2.18"></rect><line x1="7" y1="2" x2="7" y2="22"></line><line x1="17" y1="2" x2="17" y2="22"></line><line x1="2" y1="12" x2="22" y2="12"></line><line x1="2" y1="7" x2="7" y2="7"></line><line x1="2" y1="17" x2="7" y2="17"></line><line x1="17" y1="17" x2="22" y2="17"></line><line x1="17" y1="7" x2="22" y2="7"></line></svg>'
                : '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="7" width="20" height="15" rx="2" ry="2"></rect><polyline points="17 2 12 7 7 2"></polyline></svg>';

            return `
                <button class="lib-pill ${this.currentLibraryFilter === l.id ? 'active' : ''}" onclick="app.filterByLibrary(${l.id})">
                    ${iconSvg}
                    <span>${l.name} (${l.item_count})</span>
                </button>
            `;
        }).join('');
    }

    async filterByLibrary(libId) {
        this.currentLibraryFilter = libId;
        this.renderLibraryPills();
        await this.renderDynamicShelves();
    }

    async renderDynamicShelves() {
        const container = document.getElementById('dynamicShelvesContainer');
        if (!container) return;

        // If filtering by specific library
        if (this.currentLibraryFilter !== null) {
            const lib = this.libraries.find(l => l.id === this.currentLibraryFilter);
            if (!lib) {
                this.currentLibraryFilter = null;
                return this.renderDynamicShelves();
            }

            container.innerHTML = `<div style="color: var(--text-muted); padding: 24px;">Loading ${lib.name}...</div>`;
            const items = await fetch(`/api/libraries/${lib.id}/items`).then(r => r.json());

            const isMovie = lib.type === 'movies';
            const iconSvg = isMovie
                ? '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="var(--violet-primary)" stroke-width="2"><rect x="2" y="2" width="20" height="20" rx="2.18" ry="2.18"></rect><line x1="7" y1="2" x2="7" y2="22"></line><line x1="17" y1="2" x2="17" y2="22"></line><line x1="2" y1="12" x2="22" y2="12"></line><line x1="2" y1="7" x2="7" y2="7"></line><line x1="2" y1="17" x2="7" y2="17"></line><line x1="17" y1="17" x2="22" y2="17"></line><line x1="17" y1="7" x2="22" y2="7"></line></svg>'
                : '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="var(--cyan-accent)" stroke-width="2"><rect x="2" y="7" width="20" height="15" rx="2" ry="2"></rect><polyline points="17 2 12 7 7 2"></polyline></svg>';

            container.innerHTML = `
                <section class="media-shelf">
                    <div class="shelf-header">
                        <h2 class="shelf-title">
                            ${iconSvg}
                            <span>${lib.name}</span>
                            <span class="rating-badge" style="font-size: 0.72rem; margin-left: 8px;">${lib.item_count} ITEMS</span>
                        </h2>
                        <div style="display: flex; gap: 8px;">
                            <button class="shelf-action-btn" onclick="app.openAddMediaModal('single', ${lib.id})">
                                + Add Media
                            </button>
                            <button class="shelf-action-btn" onclick="app.startLibraryScan(${lib.id})">
                                ↻ Scan Library
                            </button>
                        </div>
                    </div>
                    <div class="shelf-carousel">
                        ${items && items.length > 0 ? items.map(m => this.createMediaCard(m)).join('') : '<div style="color: var(--text-muted); padding: 24px;">No items in this library yet. Click "+ Add Media" above to add some!</div>'}
                    </div>
                </section>
            `;
            return;
        }

        // Otherwise render all libraries
        if (!this.libraries || this.libraries.length === 0) {
            container.innerHTML = '<div style="color: var(--text-muted); padding: 30px;">No libraries found. Click "+ New Library" above to add one.</div>';
            return;
        }

        let shelvesHtml = '';
        for (const lib of this.libraries) {
            const isMovie = lib.type === 'movies';
            const iconSvg = isMovie
                ? '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="var(--violet-primary)" stroke-width="2"><rect x="2" y="2" width="20" height="20" rx="2.18" ry="2.18"></rect><line x1="7" y1="2" x2="7" y2="22"></line><line x1="17" y1="2" x2="17" y2="22"></line><line x1="2" y1="12" x2="22" y2="12"></line><line x1="2" y1="7" x2="7" y2="7"></line><line x1="2" y1="17" x2="7" y2="17"></line><line x1="17" y1="17" x2="22" y2="17"></line><line x1="17" y1="7" x2="22" y2="7"></line></svg>'
                : '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="var(--cyan-accent)" stroke-width="2"><rect x="2" y="7" width="20" height="15" rx="2" ry="2"></rect><polyline points="17 2 12 7 7 2"></polyline></svg>';

            shelvesHtml += `
                <section class="media-shelf" id="shelf-lib-${lib.id}">
                    <div class="shelf-header">
                        <h2 class="shelf-title">
                            ${iconSvg}
                            <span>${lib.name}</span>
                            <span class="rating-badge" style="font-size: 0.72rem; margin-left: 8px;">${lib.item_count} ITEMS</span>
                        </h2>
                        <div style="display: flex; gap: 8px;">
                            <button class="shelf-action-btn" onclick="app.openAddMediaModal('single', ${lib.id})">
                                + Add
                            </button>
                            <button class="shelf-action-btn" onclick="app.startLibraryScan(${lib.id})">
                                ↻ Scan
                            </button>
                        </div>
                    </div>
                    <div class="shelf-carousel" id="carousel-lib-${lib.id}">
                        <div style="color: var(--text-muted); padding: 16px;">Loading ${lib.name}...</div>
                    </div>
                </section>
            `;
        }
        container.innerHTML = shelvesHtml;

        // Populate items for each library shelf asynchronously
        for (const lib of this.libraries) {
            fetch(`/api/libraries/${lib.id}/items`).then(r => r.json()).then(items => {
                const el = document.getElementById(`carousel-lib-${lib.id}`);
                if (el) {
                    if (items && items.length > 0) {
                        el.innerHTML = items.map(m => this.createMediaCard(m)).join('');
                    } else {
                        el.innerHTML = `<div style="color: var(--text-muted); padding: 20px;">Library is empty. Click "+ Add" above to add media.</div>`;
                    }
                }
            }).catch(() => {});
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

            // Handle TV Series episode list & manual episode addition
            const addEpSection = document.getElementById('detailAddEpisodeSection');
            const addEpForm = document.getElementById('detailAddEpisodeForm');
            if (addEpForm) addEpForm.style.display = 'none';

            if (item.type === 'show') {
                if (addEpSection) addEpSection.style.display = 'block';

                let nextSeason = 1;
                let nextEp = 1;
                if (item.episodes && item.episodes.length > 0) {
                    const lastEp = item.episodes[item.episodes.length - 1];
                    nextSeason = lastEp.season_number || 1;
                    nextEp = (lastEp.episode_number || 0) + 1;
                }
                const epSeasonInp = document.getElementById('detailEpSeason');
                const epNumInp = document.getElementById('detailEpNumber');
                const epTitleInp = document.getElementById('detailEpTitle');
                const epFileInp = document.getElementById('detailEpFilePath');
                if (epSeasonInp) epSeasonInp.value = nextSeason;
                if (epNumInp) epNumInp.value = nextEp;
                if (epTitleInp) epTitleInp.value = '';
                if (epFileInp) epFileInp.value = '';

                if (episodeList) {
                    episodeList.style.display = 'block';
                    if (item.episodes && item.episodes.length > 0) {
                        episodeList.innerHTML = `
                            <h4 style="margin: 20px 0 12px; font-size: 1.1rem; color: #ffffff;">Episodes (${item.episodes.length})</h4>
                            ${item.episodes.map(ep => `
                                <div style="display: flex; justify-content: space-between; align-items: center; padding: 10px 14px; background: rgba(255,255,255,0.03); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); margin-bottom: 8px; cursor: pointer;" onclick="app.closeDetailModal(); app.playMediaById(${ep.id});">
                                    <div>
                                        <span style="font-weight: 700; color: #ffffff;">S${ep.season_number} E${ep.episode_number}: ${ep.title}</span>
                                        <div style="font-size: 0.8rem; color: var(--text-muted);">${ep.duration || '45m'}${ep.resolution ? ' • ' + ep.resolution : ''}</div>
                                    </div>
                                    <span class="play-circle-btn" style="width: 32px; height: 32px;"><svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg></span>
                                </div>
                            `).join('')}
                        `;
                    } else {
                        episodeList.innerHTML = `
                            <h4 style="margin: 20px 0 12px; font-size: 1.1rem; color: #ffffff;">Episodes</h4>
                            <div style="color: var(--text-muted); font-size: 0.9rem; padding: 8px 0;">No episodes added yet. Use the button below to add an episode to this series.</div>
                        `;
                    }
                }
            } else {
                if (addEpSection) addEpSection.style.display = 'none';
                if (episodeList) episodeList.style.display = 'none';
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

    toggleDetailAddEpisodeForm(open = null) {
        const form = document.getElementById('detailAddEpisodeForm');
        if (!form) return;
        const isCurrentlyOpen = form.style.display === 'block';
        const shouldOpen = open !== null ? open : !isCurrentlyOpen;
        form.style.display = shouldOpen ? 'block' : 'none';
        if (shouldOpen) {
            document.getElementById('detailEpTitle')?.focus();
        }
    }

    async submitDetailEpisode() {
        if (!this.currentMedia || !this.currentMedia.id) return;
        const season = parseInt(document.getElementById('detailEpSeason')?.value) || 1;
        const episode = parseInt(document.getElementById('detailEpNumber')?.value) || 1;
        const title = document.getElementById('detailEpTitle')?.value.trim();
        const filePath = document.getElementById('detailEpFilePath')?.value.trim();

        if (!title) {
            this.showToast('Episode title is required', 'error');
            return;
        }
        if (!filePath) {
            this.showToast('File path is required', 'error');
            return;
        }

        try {
            const res = await fetch(`/api/shows/${this.currentMedia.id}/episodes`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    title,
                    season_number: season,
                    episode_number: episode,
                    file_path: filePath
                })
            });

            const data = await res.json();
            if (res.ok) {
                this.showToast(`✓ Added S${season}E${episode}: "${title}"!`, 'success');
                this.toggleDetailAddEpisodeForm(false);
                await this.openDetailModal(this.currentMedia.id);
                this.loadCatalog();
            } else {
                this.showToast(data.detail || 'Failed to add episode', 'error');
            }
        } catch (e) {
            this.showToast(`Error: ${e.message}`, 'error');
        }
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
        this.seekOffset = 0;
        const streamUrl = `/stream/${item.id}`;
        
        const titleEl = document.getElementById('playerItemTitle');
        if (titleEl) titleEl.innerText = item.title;

        // Reset volume and unmuted state
        this.video.src = streamUrl;
        this.video.muted = false;
        this.video.volume = 1.0;
        this.setVolume(1.0);
        this.updateVolumeIcon(false, 1.0);

        const unmuteBanner = document.getElementById('playerUnmuteBanner');
        if (unmuteBanner) unmuteBanner.style.display = 'none';

        const badge = document.getElementById('playerAudioTrackBadge');
        if (badge) badge.innerText = "STEREO AAC";

        this.playerModal.classList.add('active');
        this.video.play().catch(e => {
            console.warn('Playback autoplay note:', e);
            // If browser blocked unmuted autoplay policy, play muted and prompt user to unmute
            this.video.muted = true;
            this.updateVolumeIcon(true, 1.0);
            if (unmuteBanner) unmuteBanner.style.display = 'block';
            this.video.play().catch(err => console.error('Play error', err));
        });

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
        this.seekOffset = 0;
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
        if (!this.video) return;
        const total = (this.currentMedia && this.currentMedia.duration_seconds) ? this.currentMedia.duration_seconds : this.video.duration;
        if (!total) return;

        const current = (this.seekOffset || 0) + (this.video.currentTime || 0);
        const percent = Math.min(100, Math.max(0, (current / total) * 100));

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

    seekRelative(seconds) {
        if (!this.video) return;
        const newTime = Math.max(0, (this.video.currentTime || 0) + seconds);
        this.video.currentTime = newTime;
    }

    toggleMute() {
        if (!this.video) return;
        this.video.muted = !this.video.muted;
        this.updateVolumeIcon(this.video.muted, this.video.volume);
        const unmuteBanner = document.getElementById('playerUnmuteBanner');
        if (unmuteBanner && !this.video.muted) unmuteBanner.style.display = 'none';
    }

    unmute() {
        if (!this.video) return;
        this.video.muted = false;
        if (this.video.volume < 0.1) this.video.volume = 1.0;
        this.updateVolumeIcon(false, this.video.volume);
        const slider = document.getElementById('playerVolumeSlider');
        if (slider) slider.value = this.video.volume;
        const unmuteBanner = document.getElementById('playerUnmuteBanner');
        if (unmuteBanner) unmuteBanner.style.display = 'none';
    }

    setVolume(val) {
        const v = Math.max(0, Math.min(1, parseFloat(val)));
        if (this.video) {
            this.video.volume = v;
            if (v > 0 && this.video.muted) {
                this.video.muted = false;
            }
            this.updateVolumeIcon(this.video.muted, v);
        }
        const slider = document.getElementById('playerVolumeSlider');
        if (slider) slider.value = v;
        const unmuteBanner = document.getElementById('playerUnmuteBanner');
        if (unmuteBanner && v > 0 && !this.video?.muted) unmuteBanner.style.display = 'none';
    }

    updateVolumeIcon(isMuted, volume) {
        const iconEl = document.getElementById('iconVolume');
        if (!iconEl) return;
        if (isMuted || volume <= 0.01) {
            iconEl.innerHTML = `<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="var(--crimson-accent)" stroke-width="2"><line x1="1" y1="1" x2="23" y2="23"></line><path d="M9 9v3a3 3 0 0 0 5.12 2.12M15 9.34V4a3 3 0 0 0-5.94-.6"></path><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon></svg>`;
        } else if (volume < 0.5) {
            iconEl.innerHTML = `<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon><path d="M15.54 8.46a5 5 0 0 1 0 7.07"></path></svg>`;
        } else {
            iconEl.innerHTML = `<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon><path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"></path></svg>`;
        }
    }

    forceAudioRemux() {
        if (!this.currentMedia || !this.video) return;
        const curTime = Math.floor((this.seekOffset || 0) + (this.video.currentTime || 0));
        this.video.src = `/stream/${this.currentMedia.id}?remux=1&start=${curTime}`;
        this.seekOffset = curTime;
        this.video.muted = false;
        this.video.volume = 1.0;
        this.setVolume(1.0);
        this.video.play().catch(() => {});
        const badge = document.getElementById('playerAudioTrackBadge');
        if (badge) badge.innerText = "STEREO AAC (ACTIVE)";
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

    openAddMediaModal(tab = 'single', preselectLibId = null) {
        const modal = document.getElementById('addMediaModal');
        if (!modal) return;
        modal.classList.add('active');
        this.switchAddMediaTab(tab);
        this.populateAddMediaOptions(preselectLibId);
        this.loadLibraries();
    }

    closeAddMediaModal() {
        const modal = document.getElementById('addMediaModal');
        if (modal) modal.classList.remove('active');
    }

    populateAddMediaOptions(preselectLibId = null) {
        const libSelect = document.getElementById('addMediaLibrarySelect');
        const showSelect = document.getElementById('addMediaParentShowSelect');
        const typeSelect = document.getElementById('addMediaType');

        if (libSelect) {
            libSelect.innerHTML = (this.libraries || []).map(l => `
                <option value="${l.id}" data-type="${l.type}">${l.name} (${l.type})</option>
            `).join('');
        }

        if (showSelect) {
            if (!this.showsList || this.showsList.length === 0) {
                showSelect.innerHTML = '<option value="">(No TV series found - create a TV Series first)</option>';
            } else {
                showSelect.innerHTML = this.showsList.map(s => `
                    <option value="${s.id}">${s.title} (${s.year || 'Series'})</option>
                `).join('');
            }
        }

        if (preselectLibId !== null && libSelect) {
            libSelect.value = preselectLibId;
            const chosen = (this.libraries || []).find(l => l.id === preselectLibId);
            if (chosen && typeSelect) {
                typeSelect.value = chosen.type === 'tvshows' ? 'show' : 'movie';
            }
        }

        this.onMediaTypeChange();
    }

    switchAddMediaTab(tab) {
        const tabSingle = document.getElementById('tabBtnAddSingle');
        const tabBulk = document.getElementById('tabBtnBulkAdd');
        const tabScan = document.getElementById('tabBtnScanStorage');
        const contentSingle = document.getElementById('tabContentAddSingle');
        const contentBulk = document.getElementById('tabContentBulkAdd');
        const contentScan = document.getElementById('tabContentScanStorage');

        [tabSingle, tabBulk, tabScan].forEach(btn => btn?.classList.remove('active'));
        [contentSingle, contentBulk, contentScan].forEach(cnt => cnt?.classList.remove('active'));

        if (tab === 'single') {
            tabSingle?.classList.add('active');
            contentSingle?.classList.add('active');
            this.populateAddMediaOptions();
        } else if (tab === 'bulk') {
            tabBulk?.classList.add('active');
            contentBulk?.classList.add('active');
            this.populateBulkOptions();
        } else {
            tabScan?.classList.add('active');
            contentScan?.classList.add('active');
            this.loadLibraries();
        }
    }

    populateBulkOptions() {
        const select = document.getElementById('bulkAddLibrarySelect');
        if (select) {
            select.innerHTML = (this.libraries || []).map(l => `
                <option value="${l.id}">${l.name} (${l.type.toUpperCase()}) - ${l.path}</option>
            `).join('');
        }
    }

    async submitBulkFolderImport() {
        const select = document.getElementById('bulkAddLibrarySelect');
        const libraryId = select ? parseInt(select.value) : null;
        const folderPath = document.getElementById('bulkAddFolderPath')?.value.trim();

        if (!libraryId) {
            this.showToast('Please select a destination library', 'error');
            return;
        }
        if (!folderPath) {
            this.showToast('Please provide a server directory path', 'error');
            return;
        }

        const btn = document.getElementById('btnRunBulkFolderImport');
        const progressCard = document.getElementById('bulkImportProgressCard');
        const statusText = document.getElementById('bulkImportStatusText');
        const stats = document.getElementById('bulkImportStats');

        if (btn) btn.disabled = true;
        if (progressCard) progressCard.style.display = 'block';
        if (statusText) statusText.innerText = `Scanning & importing from: ${folderPath}...`;
        if (stats) stats.innerText = 'Analyzing directory structure and technical media streams...';

        this.showToast('🚀 Bulk import in progress...', 'info');

        try {
            const res = await fetch('/api/media/bulk-add', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    library_id: libraryId,
                    mode: 'folder',
                    folder_path: folderPath
                })
            });

            const data = await res.json();
            if (res.ok) {
                const added = data.added_count || 0;
                const scanned = data.scanned_count || 0;
                this.showToast(`🎉 Bulk imported ${added} media items! (Scanned: ${scanned})`, 'success');
                if (stats) stats.innerText = `Complete: Added ${added} new items from ${scanned} scanned files.`;
                await this.loadCatalog();
                await this.loadLibraries();
            } else {
                this.showToast(data.detail || 'Bulk import failed', 'error');
                if (stats) stats.innerText = `Error: ${data.detail || 'Failed'}`;
            }
        } catch (e) {
            this.showToast(`Error: ${e.message}`, 'error');
        } finally {
            if (btn) btn.disabled = false;
        }
    }

    async submitBulkListImport() {
        const select = document.getElementById('bulkAddLibrarySelect');
        const libraryId = select ? parseInt(select.value) : null;
        const text = document.getElementById('bulkAddTextList')?.value.trim();

        if (!libraryId) {
            this.showToast('Please select a destination library', 'error');
            return;
        }
        if (!text) {
            this.showToast('Please enter at least one file path or stream URL', 'error');
            return;
        }

        const lines = text.split('\n').map(l => l.trim()).filter(l => l.length > 0);
        if (lines.length === 0) return;

        const btn = document.getElementById('btnRunBulkListImport');
        const progressCard = document.getElementById('bulkImportProgressCard');
        const statusText = document.getElementById('bulkImportStatusText');
        const stats = document.getElementById('bulkImportStats');

        if (btn) btn.disabled = true;
        if (progressCard) progressCard.style.display = 'block';
        if (statusText) statusText.innerText = `Importing ${lines.length} items...`;
        if (stats) stats.innerText = 'Extracting media metadata...';

        try {
            const res = await fetch('/api/media/bulk-add', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    library_id: libraryId,
                    mode: 'list',
                    items: lines
                })
            });

            const data = await res.json();
            if (res.ok) {
                const added = data.added_count || 0;
                this.showToast(`✨ Successfully imported ${added} items!`, 'success');
                document.getElementById('bulkAddTextList').value = '';
                if (stats) stats.innerText = `Done: Added ${added} of ${lines.length} items.`;
                await this.loadCatalog();
                await this.loadLibraries();
            } else {
                this.showToast(data.detail || 'Failed to import items', 'error');
            }
        } catch (e) {
            this.showToast(`Error: ${e.message}`, 'error');
        } finally {
            if (btn) btn.disabled = false;
        }
    }

    bulkImportFromBrowser() {
        if (this.currentBrowserPath) {
            const path = this.currentBrowserPath;
            this.closeFolderBrowser();
            this.openAddMediaModal('bulk');
            const folderInput = document.getElementById('bulkAddFolderPath');
            if (folderInput) folderInput.value = path;
        }
    }

    onMediaTypeChange() {
        const type = document.getElementById('addMediaType')?.value || 'movie';
        const groupLib = document.getElementById('groupLibrarySelect');
        const groupShow = document.getElementById('groupEpisodeSeriesSelect');
        const groupEpNums = document.getElementById('groupEpisodeNumbers');
        const groupMeta = document.getElementById('groupMovieMeta');
        const groupDirCast = document.getElementById('groupDirectorCast');
        const labelTitle = document.getElementById('labelMediaTitle');
        const libSelect = document.getElementById('addMediaLibrarySelect');

        if (type === 'movie') {
            if (groupLib) groupLib.style.display = 'block';
            if (groupShow) groupShow.style.display = 'none';
            if (groupEpNums) groupEpNums.style.display = 'none';
            if (groupMeta) groupMeta.style.display = 'grid';
            if (groupDirCast) groupDirCast.style.display = 'grid';
            if (labelTitle) labelTitle.innerHTML = 'Movie Title <span style="color: var(--amber-gold);">*</span>';

            if (libSelect && libSelect.selectedOptions && libSelect.selectedOptions[0]) {
                const curType = libSelect.selectedOptions[0].getAttribute('data-type');
                if (curType !== 'movies') {
                    for (let opt of libSelect.options) {
                        if (opt.getAttribute('data-type') === 'movies') {
                            libSelect.value = opt.value;
                            break;
                        }
                    }
                }
            }
        } else if (type === 'show') {
            if (groupLib) groupLib.style.display = 'block';
            if (groupShow) groupShow.style.display = 'none';
            if (groupEpNums) groupEpNums.style.display = 'none';
            if (groupMeta) groupMeta.style.display = 'grid';
            if (groupDirCast) groupDirCast.style.display = 'grid';
            if (labelTitle) labelTitle.innerHTML = 'Series Title <span style="color: var(--amber-gold);">*</span>';

            if (libSelect && libSelect.selectedOptions && libSelect.selectedOptions[0]) {
                const curType = libSelect.selectedOptions[0].getAttribute('data-type');
                if (curType !== 'tvshows') {
                    for (let opt of libSelect.options) {
                        if (opt.getAttribute('data-type') === 'tvshows') {
                            libSelect.value = opt.value;
                            break;
                        }
                    }
                }
            }
        } else if (type === 'episode') {
            if (groupLib) groupLib.style.display = 'none';
            if (groupShow) groupShow.style.display = 'block';
            if (groupEpNums) groupEpNums.style.display = 'grid';
            if (groupMeta) groupMeta.style.display = 'none';
            if (groupDirCast) groupDirCast.style.display = 'none';
            if (labelTitle) labelTitle.innerHTML = 'Episode Title <span style="color: var(--amber-gold);">*</span>';
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
        const type = document.getElementById('addMediaType')?.value || 'movie';
        const title = document.getElementById('addMediaTitle')?.value.trim();
        const filePath = document.getElementById('addMediaFilePath')?.value.trim() || '';
        const streamUrl = document.getElementById('addMediaStreamUrl')?.value.trim() || '';
        const synopsis = document.getElementById('addMediaSynopsis')?.value.trim() || '';

        if (!title) {
            this.showToast('Title is required', 'error');
            return;
        }

        const btn = document.getElementById('btnSubmitAddMedia');
        if (btn) btn.disabled = true;

        try {
            if (type === 'episode') {
                const showSelect = document.getElementById('addMediaParentShowSelect');
                const showId = showSelect ? parseInt(showSelect.value) : null;
                if (!showId) {
                    this.showToast('Please select a target TV Series', 'error');
                    if (btn) btn.disabled = false;
                    return;
                }
                if (!filePath && !streamUrl) {
                    this.showToast('Provide either a local file path or stream URL', 'error');
                    if (btn) btn.disabled = false;
                    return;
                }
                const seasonNumber = parseInt(document.getElementById('addMediaSeasonNum')?.value) || 1;
                const episodeNumber = parseInt(document.getElementById('addMediaEpisodeNum')?.value) || 1;

                const res = await fetch(`/api/shows/${showId}/episodes`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        title,
                        season_number: seasonNumber,
                        episode_number: episodeNumber,
                        file_path: filePath,
                        stream_url: streamUrl,
                        synopsis
                    })
                });

                const data = await res.json();
                if (res.ok) {
                    this.showToast(`✨ Added S${seasonNumber}E${episodeNumber} "${title}"!`, 'success');
                    this.closeAddMediaModal();
                    document.getElementById('formAddMedia')?.reset();
                    await this.loadCatalog();
                } else {
                    this.showToast(data.detail || 'Failed to add episode', 'error');
                }
            } else {
                if (!filePath && !streamUrl) {
                    this.showToast('Provide either a local file path or stream URL', 'error');
                    if (btn) btn.disabled = false;
                    return;
                }
                const year = parseInt(document.getElementById('addMediaYear')?.value) || 2026;
                const rating = parseFloat(document.getElementById('addMediaRating')?.value) || 8.5;
                const genre = document.getElementById('addMediaGenre')?.value.trim() || 'Cinema';
                const director = document.getElementById('addMediaDirector')?.value.trim() || '';
                const cast = document.getElementById('addMediaCast')?.value.trim() || '';
                const poster = document.getElementById('addMediaPoster')?.value.trim() || '';
                const libSelect = document.getElementById('addMediaLibrarySelect');
                const libraryId = libSelect ? parseInt(libSelect.value) : 1;

                const res = await fetch('/api/media/add', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        title,
                        type,
                        year,
                        rating,
                        genre,
                        director,
                        cast,
                        file_path: filePath,
                        stream_url: streamUrl,
                        poster,
                        synopsis,
                        library_id: libraryId
                    })
                });

                const data = await res.json();
                if (res.ok) {
                    this.showToast(`✨ Added ${type === 'show' ? 'Series' : 'Movie'} "${title}"!`, 'success');
                    this.closeAddMediaModal();
                    document.getElementById('formAddMedia')?.reset();
                    await this.loadCatalog();
                } else {
                    this.showToast(data.detail || 'Failed to add media item', 'error');
                }
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
            this.libraries = libs || [];

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
                await this.loadCatalog();
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
                await this.loadCatalog();
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
                await this.loadCatalog();
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

            const btnBulk = document.getElementById('btnBrowserBulkImport');
            if (btnBulk) {
                if (data.video_files && data.video_files.length > 0) {
                    btnBulk.style.display = 'inline-flex';
                    btnBulk.innerText = `+ Bulk Import Folder (${data.video_files.length} videos)`;
                } else {
                    btnBulk.style.display = 'none';
                }
            }

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
