/**
 * MomentMaker 原型 - 通用交互脚本
 */

// 保存草稿并跳转至「我的」
function saveDraftAndRedirect(step, extra = {}) {
  const draft = {
    step,
    ...extra,
    savedAt: new Date().toISOString()
  };
  try {
    localStorage.setItem('momentmaker_draft', JSON.stringify(draft));
  } catch (e) {
    // 原型环境 localStorage 不可用时仍给出反馈
  }
  showToast('草稿已保存');
  setTimeout(() => {
    window.location.href = 'mine.html#draft';
  }, 800);
}

function bindSaveDraftBtn(btn, step, getExtra) {
  btn?.addEventListener('click', () => {
    const extra = getExtra ? getExtra() : {};
    saveDraftAndRedirect(step, extra);
  });
}

const DEFAULT_WORK_NAME = '用户ABCD';
const WORK_NAME_KEY = 'momentmaker_work_name';

function getWorkName() {
  try {
    const stored = sessionStorage.getItem(WORK_NAME_KEY);
    if (stored && stored.trim()) return stored.trim();
  } catch (e) {
    // ignore
  }
  return DEFAULT_WORK_NAME;
}

function setWorkName(name) {
  const finalName = (name || '').trim() || DEFAULT_WORK_NAME;
  try {
    sessionStorage.setItem(WORK_NAME_KEY, finalName);
  } catch (e) {
    // ignore
  }
  return finalName;
}

// 作品名称输入（创作流程 3-4 步，点击输入框直接编辑）
function initWorkNameEditor() {
  const input = document.getElementById('workNameInput');
  if (!input) return;

  const syncInputFromStorage = () => {
    const name = getWorkName();
    input.value = name === DEFAULT_WORK_NAME ? '' : name;
    input.placeholder = DEFAULT_WORK_NAME;
  };

  syncInputFromStorage();

  input.addEventListener('blur', () => {
    setWorkName(input.value);
    syncInputFromStorage();
  });
}

function showToast(message, duration = 2500) {
  let toast = document.getElementById('toast');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'toast';
    toast.className = 'toast';
    document.body.appendChild(toast);
  }
  toast.textContent = message;
  toast.classList.add('show');
  setTimeout(() => toast.classList.remove('show'), duration);
}

// 伪进度条动画
function runProgressBar(fillEl, duration = 2000, onComplete) {
  let progress = 0;
  const interval = 50;
  const step = (100 / duration) * interval;

  if (fillEl) fillEl.style.width = '0%';

  const timer = setInterval(() => {
    progress += step;
    if (progress >= 100) {
      clearInterval(timer);
      if (fillEl) fillEl.style.width = '100%';
      if (onComplete) setTimeout(onComplete, 300);
    } else if (fillEl) {
      fillEl.style.width = progress + '%';
    }
  }, interval);

  // 无进度条元素时也保证回调执行
  if (!fillEl && onComplete) {
    setTimeout(onComplete, duration + 300);
  }
}

// 将刚生成的作品放到广场首位，形成完整的“开始创作 → 返回广场”体验
function renderLatestCreatedWork() {
  const worksGrid = document.getElementById('worksGrid');
  if (!worksGrid) return;

  let work;
  try {
    work = JSON.parse(localStorage.getItem('momentmaker_latest_work'));
  } catch (error) {
    return;
  }
  if (!work) return;

  const materialNames = {
    keychain: '钥匙扣',
    badge: '吧唧',
    postcard: '明信片'
  };

  const card = document.createElement('div');
  card.className = 'work-card';
  card.innerHTML = `
    <div class="work-card-img wf-photo ratio-medium">
      <img alt="刚生成的作品" loading="eager">
    </div>
    <div class="work-card-info">
      <div class="work-card-name"></div>
      <div class="work-card-author-row">
        <span class="work-card-author"></span>
        <span class="work-card-meta">♡ 0</span>
      </div>
    </div>
  `;

  card.querySelector('img').src = work.image;
  card.querySelector('.work-card-name').textContent = work.name || DEFAULT_WORK_NAME;
  card.querySelector('.work-card-author').textContent =
    `刚刚生成 · ${materialNames[work.material] || '创意物料'}`;
  worksGrid.prepend(card);
}

// Lightbox 控制（P1 广场页）
function initLightbox() {
  const lightbox = document.getElementById('lightbox');
  if (!lightbox) return;

  const closeBtn = lightbox.querySelector('.lightbox-close');
  const mainImg = document.getElementById('lightboxImg') || lightbox.querySelector('.lightbox-main img');
  const titleEl = lightbox.querySelector('.lightbox-title');
  const likeBtn = document.getElementById('lightboxLikeBtn');
  const likeIcon = likeBtn?.querySelector('.lightbox-like-icon');
  const likeCountEl = likeBtn?.querySelector('.lightbox-like-count');

  let liked = false;
  let likeCount = 0;

  const updateLikeUI = () => {
    if (likeCountEl) likeCountEl.textContent = String(likeCount);
    if (likeBtn) likeBtn.classList.toggle('liked', liked);
    if (likeIcon) likeIcon.textContent = liked ? '♥' : '♡';
  };

  document.querySelectorAll('.work-card').forEach(card => {
    card.addEventListener('click', () => {
      const img = card.querySelector('.work-card-img img');
      const name = card.querySelector('.work-card-name')?.textContent || '未命名作品';
      const meta = card.querySelector('.work-card-meta')?.textContent || '';
      const likeMatch = meta.match(/(\d+)/);
      likeCount = likeMatch ? parseInt(likeMatch[1], 10) : 0;
      liked = false;

      if (mainImg) {
        if (img) {
          mainImg.src = img.src;
          mainImg.style.display = 'block';
        } else {
          mainImg.removeAttribute('src');
          mainImg.style.display = 'none';
        }
      }

      if (titleEl) titleEl.textContent = name;
      updateLikeUI();
      lightbox.classList.add('active');
      document.body.style.overflow = 'hidden';
    });
  });

  likeBtn?.addEventListener('click', (e) => {
    e.stopPropagation();
    liked = !liked;
    likeCount += liked ? 1 : -1;
    updateLikeUI();
  });

  const close = () => {
    lightbox.classList.remove('active');
    document.body.style.overflow = '';
  };

  closeBtn?.addEventListener('click', close);
  lightbox.addEventListener('click', (e) => {
    if (e.target === lightbox) close();
  });
}

// 上传页交互（P2）
function initUploadPage() {
  const zone = document.getElementById('uploadZone');
  const input = document.getElementById('fileInput');
  const previewGrid = document.getElementById('previewGrid');
  const nextBtn = document.getElementById('nextBtn');
  const saveDraftBtn = document.getElementById('saveDraftBtn');
  const demoLink = document.getElementById('demoLink');
  const loadingOverlay = document.getElementById('uploadLoading');
  const templateChoices = document.querySelectorAll('#uploadTemplateList .square-template-item');
  const materialChoices = document.querySelectorAll('#materialChoiceList .material-choice-card');

  if (!zone) return;

  let files = [];
  // 广场页通过 URL 参数携带模板，例如 upload.html?template=map
  const templateFromSquare = new URLSearchParams(window.location.search).get('template');
  const availableTemplates = ['comic', 'map', 'album'];
  let selectedTemplate = availableTemplates.includes(templateFromSquare)
    ? templateFromSquare
    : 'comic';
  let selectedMaterial = 'keychain';

  // 根据广场页传入的模板值，恢复对应卡片的默认选中状态
  templateChoices.forEach(choice => {
    choice.classList.toggle('selected', choice.dataset.template === selectedTemplate);
  });

  // 将当前选择暂存起来，后续编辑页或接口可以直接读取
  const saveCreationChoices = () => {
    try {
      sessionStorage.setItem('momentmaker_creation_choices', JSON.stringify({
        template: selectedTemplate,
        material: selectedMaterial
      }));
    } catch (error) {
      // 原型在禁用浏览器存储时仍可继续完成页面交互
    }
  };

  // 原型暂未接入真实生成接口，先保存一条生成结果供广场页展示
  const saveCreatedWork = () => {
    const work = {
      name: setWorkName(document.getElementById('workNameInput')?.value),
      template: selectedTemplate,
      material: selectedMaterial,
      image: `https://picsum.photos/seed/mm-created-${Date.now()}/300/380`
    };
    try {
      localStorage.setItem('momentmaker_latest_work', JSON.stringify(work));
    } catch (error) {
      // 浏览器存储不可用时，仍允许完成页面跳转
    }
  };

  // 模板和物料均为单选：每次点击只保留一个橙色选中项
  templateChoices.forEach(choice => {
    choice.addEventListener('click', () => {
      templateChoices.forEach(item => item.classList.remove('selected'));
      choice.classList.add('selected');
      selectedTemplate = choice.dataset.template;
      saveCreationChoices();
    });
  });

  materialChoices.forEach(choice => {
    choice.addEventListener('click', () => {
      materialChoices.forEach(item => item.classList.remove('selected'));
      choice.classList.add('selected');
      selectedMaterial = choice.dataset.material;
      saveCreationChoices();
    });
  });

  const updateNextBtn = () => {
    if (nextBtn) nextBtn.disabled = files.length === 0;
  };

  const renderPreviews = () => {
    if (!previewGrid) return;
    // 预览区始终只展示一行，最多显示前 4 个素材
    const visibleFiles = files.slice(0, 4);
    previewGrid.innerHTML = visibleFiles.map((f, i) => `
      <div class="upload-preview-item">
        <img src="${f.url}" alt="预览">
        ${i === 3 && files.length > 4 ? `
          <div class="upload-preview-more" aria-label="共上传 ${files.length} 个素材">
            <span class="upload-preview-more-icon" aria-hidden="true">•••</span>
            <span class="upload-preview-more-count">+${files.length}</span>
          </div>
        ` : ''}
        <button type="button" class="upload-preview-remove" data-index="${i}" aria-label="移除此素材">×</button>
      </div>
    `).join('');

    previewGrid.querySelectorAll('.upload-preview-remove').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const idx = parseInt(btn.dataset.index);
        files.splice(idx, 1);
        renderPreviews();
        updateNextBtn();
      });
    });
  };

  const addMockFiles = (count = 4) => {
    for (let i = 0; i < count; i++) {
      files.push({
        url: `https://picsum.photos/seed/mm${i + 1}/200/200`,
        name: `sample_${i + 1}.jpg`
      });
    }
    renderPreviews();
    updateNextBtn();
  };

  zone.addEventListener('click', () => input?.click());

  zone.addEventListener('dragover', (e) => {
    e.preventDefault();
    zone.classList.add('dragover');
  });

  zone.addEventListener('dragleave', () => zone.classList.remove('dragover'));

  zone.addEventListener('drop', (e) => {
    e.preventDefault();
    zone.classList.remove('dragover');
    handleFiles(e.dataTransfer.files);
  });

  input?.addEventListener('change', (e) => handleFiles(e.target.files));

  function handleFiles(fileList) {
    Array.from(fileList).slice(0, 20 - files.length).forEach(file => {
      if (file.type.startsWith('image/') || file.type.startsWith('video/')) {
        files.push({
          url: URL.createObjectURL(file),
          name: file.name
        });
      }
    });
    renderPreviews();
    updateNextBtn();
  }

  nextBtn?.addEventListener('click', () => {
    if (files.length === 0) return;
    if (loadingOverlay) {
      loadingOverlay.classList.remove('hidden');
      const fill = loadingOverlay.querySelector('.progress-fill');
      runProgressBar(fill, 1500, () => {
        saveCreationChoices();
        saveCreatedWork();
        window.location.href = 'index.html';
      });
    } else {
      saveCreationChoices();
      saveCreatedWork();
      window.location.href = 'index.html';
    }
  });

  // 保存草稿：补充描述已移除，现在需要至少上传一个素材
  saveDraftBtn?.addEventListener('click', () => {
    if (files.length === 0) {
      showToast('请先上传素材');
      return;
    }

    saveDraftAndRedirect(1, {
      workName: setWorkName(document.getElementById('workNameInput')?.value),
      fileCount: files.length,
      template: selectedTemplate,
      material: selectedMaterial
    });
  });

  demoLink?.addEventListener('click', (e) => {
    e.preventDefault();
    addMockFiles(6);
    showToast('已载入样例素材');
    setTimeout(() => {
      if (loadingOverlay) {
        loadingOverlay.classList.remove('hidden');
        const fill = loadingOverlay.querySelector('.progress-fill');
        runProgressBar(fill, 500, () => {
          saveCreationChoices();
          saveCreatedWork();
          window.location.href = 'index.html';
        });
      } else {
        saveCreationChoices();
        saveCreatedWork();
        window.location.href = 'index.html';
      }
    }, 600);
  });

  saveCreationChoices();
  initWorkNameEditor();
  updateNextBtn();
}

// 模板选择页（P3）
function initTemplatePage() {
  const templateCards = document.querySelectorAll('.template-card');
  const styleTags = document.querySelectorAll('.style-tag');
  const materialBtns = document.querySelectorAll('.material-icon-btn');
  const previewImg = document.getElementById('templatePreview');
  const generateBtn = document.getElementById('generateBtn');
  const saveDraftBtn = document.getElementById('saveDraftBtn');

  const previews = {
    comic: {
      anime: 'https://picsum.photos/seed/comic-anime/400/560',
      cyber: 'https://picsum.photos/seed/comic-cyber/400/560',
      realistic: 'https://picsum.photos/seed/comic-real/400/560'
    },
    map: {
      anime: 'https://picsum.photos/seed/map-anime/400/560',
      cyber: 'https://picsum.photos/seed/map-cyber/400/560',
      realistic: 'https://picsum.photos/seed/map-real/400/560'
    },
    album: {
      anime: 'https://picsum.photos/seed/album-anime/400/560',
      cyber: 'https://picsum.photos/seed/album-cyber/400/560',
      realistic: 'https://picsum.photos/seed/album-real/400/560'
    }
  };

  let selectedTemplate = 'comic';
  let selectedStyle = 'anime';

  const updatePreview = () => {
    if (previewImg && previews[selectedTemplate]?.[selectedStyle]) {
      previewImg.src = previews[selectedTemplate][selectedStyle];
    }
  };

  templateCards.forEach(card => {
    card.addEventListener('click', () => {
      templateCards.forEach(c => c.classList.remove('selected'));
      card.classList.add('selected');
      selectedTemplate = card.dataset.template;
      updatePreview();
    });
  });

  styleTags.forEach(tag => {
    tag.addEventListener('click', () => {
      styleTags.forEach(t => t.classList.remove('selected'));
      tag.classList.add('selected');
      selectedStyle = tag.dataset.style;
      updatePreview();
    });
  });

  materialBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      btn.classList.toggle('selected');
    });
  });

  generateBtn?.addEventListener('click', () => {
    generateBtn.disabled = true;
    generateBtn.textContent = '生成中...';
    setTimeout(() => {
      window.location.href = 'index.html';
    }, 1200);
  });

  bindSaveDraftBtn(saveDraftBtn, 2, () => ({
    template: selectedTemplate,
    style: selectedStyle,
    materials: Array.from(materialBtns)
      .filter(btn => btn.classList.contains('selected'))
      .map(btn => btn.textContent.trim())
  }));

  updatePreview();
}

// 我的页面（P6）
function initProfilePage() {
  const tabs = document.querySelectorAll('.profile-tab');
  const panelPublished = document.getElementById('panel-published');
  const panelDraft = document.getElementById('panel-draft');
  const demoEntry = document.getElementById('demoEntry');

  const switchPanel = (panel) => {
    tabs.forEach(t => t.classList.toggle('active', t.dataset.panel === panel));
    if (panelPublished) panelPublished.style.display = panel === 'published' ? 'block' : 'none';
    if (panelDraft) panelDraft.style.display = panel === 'draft' ? 'block' : 'none';
  };

  tabs.forEach(tab => {
    tab.addEventListener('click', () => switchPanel(tab.dataset.panel));
  });

  // 从上传页保存草稿跳转过来时，自动打开草稿 Tab
  if (window.location.hash === '#draft') {
    switchPanel('draft');
  }

  demoEntry?.addEventListener('click', () => {
    window.location.href = 'upload.html';
  });
}

// 顶部 Banner 轮播（广场页：海报 + 每位选手各一屏，5 秒自动切换）
function initKingkongCarousel() {
  const track = document.getElementById('kingkongTrack');
  const dots = document.querySelectorAll('.kingkong-dot');
  const viewport = document.querySelector('.kingkong-viewport');
  if (!track || dots.length === 0) return;

  const slides = track.querySelectorAll('.kingkong-slide');
  let current = 0;
  let startX = 0;
  let isDragging = false;
  let autoTimer = null;
  const AUTO_INTERVAL = 5000;

  const goTo = (index) => {
    current = Math.max(0, Math.min(index, slides.length - 1));
    track.style.transform = `translateX(-${current * 100}%)`;
    dots.forEach((dot, i) => dot.classList.toggle('active', i === current));
  };

  const startAutoPlay = () => {
    stopAutoPlay();
    autoTimer = setInterval(() => {
      goTo((current + 1) % slides.length);
    }, AUTO_INTERVAL);
  };

  const stopAutoPlay = () => {
    if (autoTimer) {
      clearInterval(autoTimer);
      autoTimer = null;
    }
  };

  const resetAutoPlay = () => {
    startAutoPlay();
  };

  dots.forEach((dot, i) => {
    dot.addEventListener('click', () => {
      goTo(i);
      resetAutoPlay();
    });
  });

  viewport?.addEventListener('touchstart', (e) => {
    startX = e.touches[0].clientX;
    isDragging = true;
    stopAutoPlay();
  }, { passive: true });

  viewport?.addEventListener('touchend', (e) => {
    if (!isDragging) return;
    const diff = e.changedTouches[0].clientX - startX;
    if (Math.abs(diff) > 40) {
      goTo(diff < 0 ? current + 1 : current - 1);
    }
    isDragging = false;
    resetAutoPlay();
  }, { passive: true });

  goTo(0);
  startAutoPlay();
}

// 页面初始化入口
document.addEventListener('DOMContentLoaded', () => {
  initKingkongCarousel();
  renderLatestCreatedWork();
  initLightbox();
  initUploadPage();
  initTemplatePage();
  initProfilePage();
});
