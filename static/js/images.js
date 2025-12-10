// Images Tab - View Screenshots and CAPTCHA Images

function loadImagesTab() {
    const container = document.getElementById('tab-images');
    container.innerHTML = `
        <div class="space-y-6">
            
            <!-- Filter Controls -->
            <div class="stat-card">
                <div class="flex items-center justify-between mb-4">
                    <h2 class="text-xl font-bold">📸 Screenshots & CAPTCHA Images</h2>
                    <button onclick="loadImages()" class="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded text-sm">
                        🔄 Refresh
                    </button>
                </div>
                
                <div class="flex gap-4">
                    <button onclick="showImageType('screenshots')" id="btn-screenshots" class="tab-button active">
                        📸 Screenshots
                    </button>
                    <button onclick="showImageType('captcha')" id="btn-captcha" class="tab-button">
                        🔐 CAPTCHA Images
                    </button>
                </div>
            </div>

            <!-- Screenshots Section -->
            <div id="screenshots-section" class="stat-card">
                <h3 class="text-lg font-bold mb-4">Error Screenshots (Last 50)</h3>
                <p class="text-gray-400 text-sm mb-4">Screenshots are captured when submissions fail</p>
                <div id="screenshots-gallery" class="image-gallery">
                    <p class="text-gray-400 text-center py-8 col-span-full">Loading...</p>
                </div>
            </div>

            <!-- CAPTCHA Images Section -->
            <div id="captcha-section" class="stat-card hidden">
                <h3 class="text-lg font-bold mb-4">CAPTCHA Images (Original vs Preprocessed)</h3>
                <p class="text-gray-400 text-sm mb-4">View OCR preprocessing to debug accuracy</p>
                <div id="captcha-gallery" class="space-y-6">
                    <p class="text-gray-400 text-center py-8">Loading...</p>
                </div>
            </div>

        </div>
    `;
}

function showImageType(type) {
    // Update button states
    document.querySelectorAll('#tab-images .tab-button').forEach(btn => btn.classList.remove('active'));
    
    if (type === 'screenshots') {
        document.getElementById('btn-screenshots').classList.add('active');
        document.getElementById('screenshots-section').classList.remove('hidden');
        document.getElementById('captcha-section').classList.add('hidden');
    } else {
        document.getElementById('btn-captcha').classList.add('active');
        document.getElementById('screenshots-section').classList.add('hidden');
        document.getElementById('captcha-section').classList.remove('hidden');
    }
}

async function loadImages() {
    loadScreenshots();
    loadCaptchaImages();
}

async function loadScreenshots() {
    try {
        const response = await fetch('/api/screenshots');
        const data = await response.json();

        const gallery = document.getElementById('screenshots-gallery');
        
        if (data.screenshots.length === 0) {
            gallery.innerHTML = '<p class="text-gray-400 text-center py-8 col-span-full">No screenshots available</p>';
            return;
        }

        gallery.innerHTML = data.screenshots.map(screenshot => `
            <div class="image-card" onclick="openImageModal('${screenshot.url}')">
                <img src="${screenshot.url}" alt="Screenshot" loading="lazy">
                <p class="text-xs text-gray-400 mt-2 truncate" title="${screenshot.log_id}">
                    ${screenshot.log_id.substring(0, 16)}...
                </p>
            </div>
        `).join('');

    } catch (error) {
        console.error('Error loading screenshots:', error);
        document.getElementById('screenshots-gallery').innerHTML = 
            '<p class="text-red-400 text-center py-8 col-span-full">Error loading screenshots</p>';
    }
}

async function loadCaptchaImages() {
    try {
        const response = await fetch('/api/captcha-images');
        const data = await response.json();

        const gallery = document.getElementById('captcha-gallery');
        
        const captchaEntries = Object.entries(data.captcha_images);
        
        if (captchaEntries.length === 0) {
            gallery.innerHTML = '<p class="text-gray-400 text-center py-8">No CAPTCHA images available</p>';
            return;
        }

        // Only show first 20 to avoid overload
        gallery.innerHTML = captchaEntries.slice(0, 20).map(([logId, images]) => {
            const original = images.find(img => img.type === 'original');
            const preprocessed = images.filter(img => img.type === 'preprocessed');
            
            return `
                <div class="stat-card">
                    <h4 class="font-mono text-xs text-gray-400 mb-3">${logId}</h4>
                    <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
                        ${original ? `
                            <div class="image-card" onclick="openImageModal('${original.url}')">
                                <img src="${original.url}" alt="Original CAPTCHA" loading="lazy">
                                <p class="text-xs text-center mt-2 text-gray-400">Original</p>
                            </div>
                        ` : ''}
                        ${preprocessed.map(img => `
                            <div class="image-card" onclick="openImageModal('${img.url}')">
                                <img src="${img.url}" alt="Preprocessed CAPTCHA" loading="lazy">
                                <p class="text-xs text-center mt-2 text-gray-400">${img.filename.split('_').slice(-1)[0].replace('.png', '')}</p>
                            </div>
                        `).join('')}
                    </div>
                </div>
            `;
        }).join('');

    } catch (error) {
        console.error('Error loading CAPTCHA images:', error);
        document.getElementById('captcha-gallery').innerHTML = 
            '<p class="text-red-400 text-center py-8">Error loading CAPTCHA images</p>';
    }
}