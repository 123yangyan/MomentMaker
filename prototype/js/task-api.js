/**
 * MomentMaker 前后端联调 API 客户端。
 * 统一使用后端单数路径：/api/upload、/api/task/start、/api/task/{id}/status
 */
(function exposeApi(global) {
  'use strict';

  const API_BASE = 'http://127.0.0.1:8000';
  const POLL_INTERVAL = 2000;

  function getSessionId() {
    return global.MomentMakerUploadLabels?.getOrCreateSessionId();
  }

  /** 把后端返回的相对路径拼成完整图片地址 */
  function fileUrl(path) {
    if (!path) return '';
    if (path.startsWith('http')) return path;
    return `${API_BASE}${path}`;
  }

  async function request(path, options = {}) {
    let response;
    try {
      response = await global.fetch(`${API_BASE}${path}`, options);
    } catch (error) {
      throw new Error('网络连接失败，请确认后端已启动');
    }

    let body;
    try {
      body = await response.json();
    } catch (error) {
      throw new Error('服务器返回了无法识别的数据');
    }

    if (!response.ok || body?.code !== 200) {
      throw new Error(body?.message || `请求失败（HTTP ${response.status}）`);
    }
    return body;
  }

  /** 上传 1～20 张图片，返回 file_ids 和 previews */
  async function uploadFiles(files) {
    const sessionId = getSessionId();
    if (!sessionId) throw new Error('无法创建匿名会话，请检查浏览器存储设置');

    const formData = new FormData();
    Array.from(files).forEach((file) => formData.append('files', file));

    const body = await request('/api/upload', {
      method: 'POST',
      headers: { 'X-Session-Id': sessionId },
      body: formData
    });
    return body.data;
  }

  /** 创建生成任务，立即返回 task_id */
  async function startTask(payload) {
    const sessionId = getSessionId();
    const body = await request('/api/task/start', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Session-Id': sessionId
      },
      body: JSON.stringify({
        file_ids: payload.file_ids,
        template: payload.template,
        style: payload.style || 'anime',
        material: payload.material,
        work_title: payload.work_title,
        story_text: payload.story_text || null
      })
    });
    return body.data;
  }

  /** 查询任务当前状态 */
  async function getTaskStatus(taskId) {
    const sessionId = getSessionId();
    const body = await request(`/api/task/${encodeURIComponent(taskId)}/status`, {
      headers: { 'X-Session-Id': sessionId }
    });
    return body.data;
  }

  /**
   * 每 2 秒轮询任务，直到 succeeded 或 failed。
   * 返回 { stop } 供页面卸载时停止轮询。
   */
  function pollTask(taskId, callbacks = {}) {
    let timer = null;
    let stopped = false;

    const stop = () => {
      stopped = true;
      if (timer) global.clearTimeout(timer);
      timer = null;
    };

    const tick = async () => {
      if (stopped) return;
      try {
        const data = await getTaskStatus(taskId);
        if (data.status === 'succeeded') {
          stop();
          callbacks.onDone?.(data);
          return;
        }
        if (data.status === 'failed') {
          stop();
          callbacks.onFailed?.(data);
          return;
        }
        callbacks.onUpdate?.(data);
        timer = global.setTimeout(tick, POLL_INTERVAL);
      } catch (error) {
        callbacks.onError?.(error);
        timer = global.setTimeout(tick, POLL_INTERVAL);
      }
    };

    tick();
    return { stop };
  }

  /** 发布已完成任务到广场 */
  async function publishWork(taskId, material, nickname) {
    const sessionId = getSessionId();
    const body = await request('/api/works', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Session-Id': sessionId
      },
      body: JSON.stringify({
        task_id: taskId,
        material: Array.isArray(material) ? material : [material],
        nickname: nickname || '匿名用户'
      })
    });
    return body.data;
  }

  async function fetchWorks(page = 1) {
    const body = await request(`/api/works?page=${page}&page_size=24`);
    return body.data;
  }

  async function fetchWorkDetail(workId) {
    const body = await request(`/api/works/${encodeURIComponent(workId)}`);
    return body.data;
  }

  async function likeWork(workId) {
    const body = await request(`/api/works/${encodeURIComponent(workId)}/like`, {
      method: 'POST'
    });
    return body.data;
  }

  async function fetchMyTasks() {
    const sessionId = getSessionId();
    const body = await request('/api/task/mine', {
      headers: { 'X-Session-Id': sessionId }
    });
    return body.data.items;
  }

  async function fetchMyWorks() {
    const sessionId = getSessionId();
    const body = await request('/api/works/mine', {
      headers: { 'X-Session-Id': sessionId }
    });
    return body.data.items;
  }

  const STATUS_LABELS = {
    pending: '任务已创建',
    scoring: 'AI 正在识别素材',
    selecting: '正在筛选最佳图片',
    generating: '正在生成海报',
    downloading: '正在保存成品',
    succeeded: '生成完成',
    failed: '生成失败'
  };

  const ERROR_MESSAGES = {
    missing_api_key: '生成服务暂时不可用，请稍后再试',
    insufficient_scores: '没有成功识别的人物照片，请换几张更清晰的正面照重试',
    http_error: '模型服务暂时繁忙，请稍后重试',
    request_failed: '模型服务暂时繁忙，请稍后重试',
    empty_result: '海报生成没有返回图片，请重新提交',
    invalid_response: '模型返回异常，请重新提交',
    server_restarted: '服务刚重启，请重新提交这次创作',
    internal_error: '任务处理失败，请稍后重试'
  };

  /** 根据任务状态生成副标题，避免生图阶段仍显示评分进度 */
  function progressSubtitle(data) {
    const completed = data.completed_images ?? 0;
    const total = data.total_images ?? 0;
    const failed = data.failed_images ?? 0;
    const selected = data.selected_count ?? (data.selected_file_ids || []).length;
    switch (data.status) {
      case 'pending':
        return '马上开始评分，请稍候';
      case 'scoring':
        return failed
          ? `已完成 ${completed}/${total} 张评分，${failed} 张失败仍继续`
          : `已完成 ${completed}/${total} 张评分`;
      case 'selecting':
        return selected ? `已选出 ${selected} 张最佳参考图` : '正在比较分数，选出最佳参考图';
      case 'generating':
        return selected ? `正在用 ${selected} 张参考图生成海报` : '正在生成海报，大约需要一两分钟';
      case 'downloading':
        return '海报已生成，正在保存到本地';
      case 'succeeded':
        return '海报已经准备好';
      case 'failed':
        return ERROR_MESSAGES[data.error_code] || data.error_message || '生成失败，请稍后重试';
      default:
        return `当前进度 ${data.progress || 0}%`;
    }
  }

  function friendlyError(taskData) {
    if (!taskData) return '生成失败，请稍后重试';
    return ERROR_MESSAGES[taskData.error_code] || taskData.error_message || '生成失败，请稍后重试';
  }

  global.MomentMakerApi = Object.freeze({
    API_BASE,
    fileUrl,
    uploadFiles,
    startTask,
    getTaskStatus,
    pollTask,
    publishWork,
    fetchWorks,
    fetchWorkDetail,
    likeWork,
    fetchMyTasks,
    fetchMyWorks,
    STATUS_LABELS,
    ERROR_MESSAGES,
    progressSubtitle,
    friendlyError
  });

  // 兼容旧引用名
  global.MomentMakerTaskApi = global.MomentMakerApi;
})(window);
