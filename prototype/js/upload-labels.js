/**
 * MomentMaker 上传标签模块。
 * 只生成 POST /api/uploads 所需的匿名设备标签、图片标签和 SHA-256；
 * 不上传文件、不读取图片内容语义，也不采集手机号、定位或硬件唯一标识。
 */
(function exposeUploadLabels(global) {
  'use strict';

  const SESSION_KEY = 'momentmaker_session_id';

  function createUuid() {
    if (global.crypto?.randomUUID) return global.crypto.randomUUID();
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, char => {
      const random = Math.floor(Math.random() * 16);
      const value = char === 'x' ? random : (random & 0x3) | 0x8;
      return value.toString(16);
    });
  }

  function getOrCreateSessionId() {
    try {
      const stored = global.localStorage.getItem(SESSION_KEY);
      if (stored) return stored;
      const sessionId = createUuid();
      global.localStorage.setItem(SESSION_KEY, sessionId);
      return sessionId;
    } catch (error) {
      // 存储被禁用时仅维持当前页面会话，不采集其他身份信息作为替代。
      return createUuid();
    }
  }

  function detectDevice(userAgent) {
    const androidModel = userAgent.match(/Android[^;]*;\s*([^;)]+?)(?:\s+Build\/|;|\))/i)?.[1]?.trim();
    if (/iPhone/i.test(userAgent)) return { manufacturer: 'Apple', model: 'iPhone' };
    if (/iPad/i.test(userAgent)) return { manufacturer: 'Apple', model: 'iPad' };
    if (/Android/i.test(userAgent)) return { manufacturer: null, model: androidModel || null };
    return { manufacturer: null, model: null };
  }

  function collectDeviceInfo() {
    const navigatorInfo = global.navigator || {};
    const screenInfo = global.screen || {};
    const connection = navigatorInfo.connection || navigatorInfo.mozConnection || navigatorInfo.webkitConnection;
    const detected = detectDevice(navigatorInfo.userAgent || '');

    return {
      device_type: navigatorInfo.maxTouchPoints > 0 ? 'mobile_or_tablet' : 'desktop',
      manufacturer: detected.manufacturer,
      model: detected.model,
      platform: navigatorInfo.platform || null,
      user_agent: navigatorInfo.userAgent || null,
      language: navigatorInfo.language || null,
      languages: Array.from(navigatorInfo.languages || []),
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || null,
      screen: {
        width: Number(screenInfo.width) || null,
        height: Number(screenInfo.height) || null,
        available_width: Number(screenInfo.availWidth) || null,
        available_height: Number(screenInfo.availHeight) || null,
        pixel_ratio: Number(global.devicePixelRatio) || 1,
        orientation: global.matchMedia?.('(orientation: portrait)').matches ? 'portrait' : 'landscape'
      },
      capabilities: {
        touch_supported: Number(navigatorInfo.maxTouchPoints) > 0,
        max_touch_points: Number(navigatorInfo.maxTouchPoints) || 0,
        hardware_concurrency: Number(navigatorInfo.hardwareConcurrency) || null,
        device_memory_gb: Number(navigatorInfo.deviceMemory) || null
      },
      network: connection ? {
        effective_type: connection.effectiveType || null,
        downlink_mbps: Number(connection.downlink) || null,
        save_data: Boolean(connection.saveData)
      } : null
    };
  }

  function assertImage(file) {
    if (!(file instanceof File) || !file.type.startsWith('image/')) {
      throw new TypeError(`仅支持图片文件：${file?.name || '未知文件'}`);
    }
  }

  async function sha256(file) {
    if (!global.crypto?.subtle) throw new Error('当前浏览器不支持 SHA-256 完整性校验');
    const digest = await global.crypto.subtle.digest('SHA-256', await file.arrayBuffer());
    return Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, '0')).join('');
  }

  async function buildManifest(files) {
    const imageFiles = Array.from(files);
    if (imageFiles.length < 1 || imageFiles.length > 20) {
      throw new RangeError('请选择 1～20 张图片');
    }

    imageFiles.forEach(assertImage);
    const labels = await Promise.all(imageFiles.map(async (file, index) => ({
      client_file_id: `local_${String(index + 1).padStart(3, '0')}`,
      filename: file.name,
      mime_type: file.type,
      size_bytes: file.size,
      last_modified: file.lastModified || null,
      sha256: await sha256(file)
    })));

    return {
      schema_version: '1.0',
      session_id: getOrCreateSessionId(),
      device: collectDeviceInfo(),
      files: labels
    };
  }

  global.MomentMakerUploadLabels = Object.freeze({
    getOrCreateSessionId,
    collectDeviceInfo,
    buildManifest
  });
})(window);
