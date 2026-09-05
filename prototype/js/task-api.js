/**
 * MomentMaker 创建生成任务模块。
 * 输入来自 POST /api/uploads 的响应和 upload-labels.js 已保存的任务草稿；
 * 输出 task_id，并只轮询任务是否开始、是否结束。本模块不读取后端内部处理阶段。
 */
(function exposeTaskApi(global) {
  'use strict';

  const API_BASE = '/api';
  const TASK_PAYLOAD_KEY = 'momentmaker_task_payload';
  const ACTIVE_TASK_KEY = 'momentmaker_active_task';
  const VALID_TEMPLATES = new Set(['comic', 'map', 'album']);
  const VALID_STYLES = new Set(['anime', 'cyber', 'realistic']);
  const VALID_MATERIALS = new Set(['badge', 'postcard', 'keychain']);
  const POLL_INTERVAL = 2000;
  const TASK_TIMEOUT = 3 * 60 * 1000;
  let pendingRequest = null;
  let pollTimer = null;
  let pollController = null;
  let pollingTaskId = null;

  function readTaskDraft() {
    try {
      const draft = JSON.parse(global.sessionStorage.getItem(TASK_PAYLOAD_KEY));
      if (!draft) throw new Error('缺少生成任务参数，请重新选择图片');
      return draft;
    } catch (error) {
      if (error instanceof SyntaxError) throw new Error('生成任务参数格式错误，请重新操作');
      throw error;
    }
  }

  function getUploadData(uploadResponse) {
    const data = uploadResponse?.data?.data || uploadResponse?.data || uploadResponse;
    const uploadId = data?.upload_id;
    const files = Array.isArray(data?.files) ? data.files : [];
    const fileIds = files.map(file => file?.file_id).filter(Boolean);

    if (!uploadId) throw new Error('上传响应缺少 upload_id');
    if (fileIds.length < 3 || fileIds.length > 20) {
      throw new Error('生成任务需要 3～20 张已上传图片');
    }
    if (fileIds.length !== new Set(fileIds).size) throw new Error('上传响应包含重复 file_id');

    return { uploadId, fileIds };
  }

  function buildPayload(uploadResponse, taskDraft = readTaskDraft()) {
    const { uploadId, fileIds } = getUploadData(uploadResponse);
    const workName = String(taskDraft.work_name || '').trim();

    if (!workName || workName.length > 30) throw new Error('作品名称必须为 1～30 个字符');
    if (!VALID_TEMPLATES.has(taskDraft.template)) throw new Error('模板类型无效');
    if (!VALID_STYLES.has(taskDraft.style)) throw new Error('视觉风格无效');
    if (!VALID_MATERIALS.has(taskDraft.material)) throw new Error('物料类型无效');

    return {
      schema_version: '1.0',
      upload_id: uploadId,
      file_ids: fileIds,
      work_name: workName,
      template: taskDraft.template,
      style: taskDraft.style,
      material: taskDraft.material
    };
  }

  async function sendCreateRequest(payload, retryContext = {}) {
    const sessionId = global.MomentMakerUploadLabels?.getOrCreateSessionId();
    if (!sessionId) throw new Error('无法创建匿名会话，请检查浏览器存储设置');

    let response;
    try {
      response = await global.fetch(`${API_BASE}/tasks`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Session-Id': sessionId
        },
        body: JSON.stringify(payload)
      });
    } catch (error) {
      throw new Error('网络连接失败，暂时无法创建生成任务');
    }

    let body;
    try {
      body = await response.json();
    } catch (error) {
      throw new Error('创建任务接口返回了无法识别的数据');
    }

    if (!response.ok || body?.code !== 0) {
      throw new Error(body?.message || `创建生成任务失败（HTTP ${response.status}）`);
    }

    const task = body?.data;
    if (!task?.task_id) throw new Error('创建任务接口未返回 task_id');

    const activeTask = {
      task_id: task.task_id,
      started: Boolean(task.started),
      done: Boolean(task.done),
      result_url: task.result_url || null,
      error: task.error || null,
      retry_count: retryContext.retryCount || 0,
      previous_task_id: retryContext.previousTaskId || null,
      request_payload: payload,
      created_at: new Date().toISOString()
    };
    global.sessionStorage.setItem(ACTIVE_TASK_KEY, JSON.stringify(activeTask));
    return activeTask;
  }

  function createTask(uploadResponse, taskDraft) {
    // POST 不自动重试；同一页面只复用进行中的请求，避免重复创建任务。
    if (pendingRequest) return pendingRequest;
    const payload = buildPayload(uploadResponse, taskDraft);
    pendingRequest = sendCreateRequest(payload, { retryCount: 0 }).finally(() => {
      pendingRequest = null;
    });
    return pendingRequest;
  }

  function getActiveTask() {
    try {
      return JSON.parse(global.sessionStorage.getItem(ACTIVE_TASK_KEY));
    } catch (error) {
      return null;
    }
  }

  function saveActiveTask(task) {
    const previous = getActiveTask();
    const activeTask = {
      task_id: task.task_id,
      started: task.started,
      done: task.done,
      result_url: task.result_url,
      error: task.error,
      retry_count: previous?.retry_count || 0,
      previous_task_id: previous?.previous_task_id || null,
      request_payload: previous?.request_payload || null,
      created_at: previous?.task_id === task.task_id ? previous.created_at : new Date().toISOString(),
      updated_at: new Date().toISOString()
    };
    global.sessionStorage.setItem(ACTIVE_TASK_KEY, JSON.stringify(activeTask));
    return activeTask;
  }

  async function getTask(taskId, signal) {
    if (!taskId) throw new Error('缺少 task_id，无法查询任务');
    const sessionId = global.MomentMakerUploadLabels?.getOrCreateSessionId();
    if (!sessionId) throw new Error('无法读取匿名会话');

    let response;
    try {
      response = await global.fetch(`${API_BASE}/tasks/${encodeURIComponent(taskId)}`, {
        method: 'GET',
        headers: { 'X-Session-Id': sessionId },
        signal
      });
    } catch (error) {
      if (error.name === 'AbortError') throw error;
      throw new Error('网络连接失败，暂时无法查询任务');
    }

    let body;
    try {
      body = await response.json();
    } catch (error) {
      throw new Error('任务查询接口返回了无法识别的数据');
    }

    if (!response.ok || body?.code !== 0) {
      throw new Error(body?.message || `查询任务失败（HTTP ${response.status}）`);
    }

    const task = body?.data;
    if (!task || task.task_id !== taskId) throw new Error('任务查询结果与当前 task_id 不一致');
    if (typeof task.started !== 'boolean' || typeof task.done !== 'boolean') {
      throw new Error('任务查询结果缺少 started 或 done');
    }

    return {
      task_id: task.task_id,
      started: task.started,
      done: task.done,
      result_url: task.result_url || null,
      error: task.error || null
    };
  }

  function stopPolling() {
    if (pollTimer) global.clearTimeout(pollTimer);
    if (pollController) pollController.abort();
    pollTimer = null;
    pollController = null;
    pollingTaskId = null;
  }

  function startPolling(taskId, callbacks = {}) {
    stopPolling();
    let currentTaskId = taskId;
    pollingTaskId = currentTaskId;
    let startedWasReported = Boolean(getActiveTask()?.started);
    const sessionIdAtStart = global.MomentMakerUploadLabels?.getOrCreateSessionId();

    const scheduleNext = () => {
      if (pollingTaskId !== currentTaskId) return;
      pollTimer = global.setTimeout(pollOnce, POLL_INTERVAL);
    };

    const pollOnce = async () => {
      if (pollingTaskId !== currentTaskId) return;
      const storedTask = getActiveTask();
      if (storedTask?.task_id && storedTask.task_id !== currentTaskId) {
        stopPolling();
        callbacks.onPaused?.('active_task_changed');
        return;
      }
      if (global.MomentMakerUploadLabels?.getOrCreateSessionId() !== sessionIdAtStart) {
        stopPolling();
        callbacks.onPaused?.('session_changed');
        return;
      }
      if (global.navigator?.onLine === false) {
        stopPolling();
        callbacks.onPaused?.('offline');
        return;
      }
      pollController = new AbortController();

      try {
        const task = saveActiveTask(await getTask(currentTaskId, pollController.signal));
        callbacks.onUpdate?.(task);

        if (task.started && !startedWasReported) {
          startedWasReported = true;
          callbacks.onStarted?.(task);
        }

        if (task.done) {
          stopPolling();
          if (task.error) callbacks.onFailed?.(task);
          else callbacks.onDone?.(task);
          return;
        }

        const elapsed = Date.now() - Date.parse(task.created_at);
        if (elapsed >= TASK_TIMEOUT) {
          if (task.retry_count >= 1 || !task.request_payload) {
            stopPolling();
            callbacks.onManualRetryRequired?.(task);
            return;
          }

          callbacks.onRetrying?.(task);
          const previousTaskId = currentTaskId;
          global.sessionStorage.setItem(ACTIVE_TASK_KEY, JSON.stringify({
            ...task,
            retry_count: 1,
            updated_at: new Date().toISOString()
          }));
          const retriedTask = await sendCreateRequest(task.request_payload, {
            retryCount: 1,
            previousTaskId
          });
          currentTaskId = retriedTask.task_id;
          pollingTaskId = currentTaskId;
          startedWasReported = Boolean(retriedTask.started);
          callbacks.onRestarted?.(retriedTask, previousTaskId);
        }

        scheduleNext();
      } catch (error) {
        if (error.name === 'AbortError') return;
        callbacks.onPollError?.(error);
        scheduleNext();
      }
    };

    pollOnce();
  }

  function retryActiveTaskManually() {
    const task = getActiveTask();
    if (!task?.request_payload) return Promise.reject(new Error('缺少原任务参数，无法重新发起'));
    if (pendingRequest) return pendingRequest;

    stopPolling();
    pendingRequest = sendCreateRequest(task.request_payload, {
      retryCount: 0,
      previousTaskId: task.task_id
    }).finally(() => {
      pendingRequest = null;
    });
    return pendingRequest;
  }

  function resumeActiveTask(callbacks = {}) {
    const task = getActiveTask();
    if (!task?.task_id || task.done) return false;
    startPolling(task.task_id, callbacks);
    return true;
  }

  global.addEventListener?.('pagehide', stopPolling);

  global.MomentMakerTaskApi = Object.freeze({
    buildPayload,
    createTask,
    getActiveTask,
    getTask,
    startPolling,
    stopPolling,
    resumeActiveTask,
    retryActiveTaskManually
  });
})(window);
