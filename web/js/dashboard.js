const state = {
      fileName: '',
      rawPosts: [],
      posts: [],
      filteredPosts: [],
      comments: [],
      filteredComments: [],
      users: new Map(),
      expandedPostId: null,
      activeTab: 'dashboard',
      language: 'ru',
      localExports: [],
      schedulerEnabled: false
    };

    const el = {
      appVersion: document.getElementById('appVersion'),
      fileInput: document.getElementById('jsonFile'),
      selectedFileName: document.getElementById('selectedFileName'),
      localExportSelect: document.getElementById('localExportSelect'),
      localExportSort: document.getElementById('localExportSort'),
      openLocalExport: document.getElementById('openLocalExport'),
      localExportStatus: document.getElementById('localExportStatus'),
      themeToggle: document.getElementById('themeToggle'),
      languageSelect: document.getElementById('languageSelect'),
      tabs: document.querySelectorAll('.tab'),
      dashboardView: document.getElementById('dashboardView'),
      postsView: document.getElementById('postsView'),
      exportView: document.getElementById('exportView'),
      searchText: document.getElementById('searchText'),
      filterUserId: document.getElementById('filterUserId'),
      filterUsername: document.getElementById('filterUsername'),
      filterDateFrom: document.getElementById('filterDateFrom'),
      filterDateTo: document.getElementById('filterDateTo'),
      filterEmoji: document.getElementById('filterEmoji'),
      filterMedia: document.getElementById('filterMedia'),
      filterReplies: document.getElementById('filterReplies'),
      metricFile: document.getElementById('metricFile'),
      metricPosts: document.getElementById('metricPosts'),
      metricComments: document.getElementById('metricComments'),
      metricUsers: document.getElementById('metricUsers'),
      metricReactions: document.getElementById('metricReactions'),
      commentsByDayChart: document.getElementById('commentsByDayChart'),
      topUsersChart: document.getElementById('topUsersChart'),
      topEmojiChart: document.getElementById('topEmojiChart'),
      topPostsChart: document.getElementById('topPostsChart'),
      daysStatus: document.getElementById('daysStatus'),
      usersStatus: document.getElementById('usersStatus'),
      emojiStatus: document.getElementById('emojiStatus'),
      postsStatus: document.getElementById('postsStatus'),
      tableStatus: document.getElementById('tableStatus'),
      postsBody: document.getElementById('postsBody'),
      drawerBackdrop: document.getElementById('drawerBackdrop'),
      userDrawer: document.getElementById('userDrawer'),
      drawerUserName: document.getElementById('drawerUserName'),
      drawerUserMeta: document.getElementById('drawerUserMeta'),
      drawerBody: document.getElementById('drawerBody'),
      closeDrawer: document.getElementById('closeDrawer'),
      exportChannel: document.getElementById('exportChannel'),
      configTelegramSession: document.getElementById('configTelegramSession'),
      configApiId: document.getElementById('configApiId'),
      configApiHash: document.getElementById('configApiHash'),
      configOutputFile: document.getElementById('configOutputFile'),
      configPostLimit: document.getElementById('configPostLimit'),
      configIncrementalLookbackPosts: document.getElementById('configIncrementalLookbackPosts'),
      configPostsPauseSeconds: document.getElementById('configPostsPauseSeconds'),
      configPostsPauseAfterPosts: document.getElementById('configPostsPauseAfterPosts'),
      configPostgresHost: document.getElementById('configPostgresHost'),
      configPostgresPort: document.getElementById('configPostgresPort'),
      configPostgresDb: document.getElementById('configPostgresDb'),
      configPostgresUser: document.getElementById('configPostgresUser'),
      configPostgresPassword: document.getElementById('configPostgresPassword'),
      configPostgresTable: document.getElementById('configPostgresTable'),
      configLlmEndpoint: document.getElementById('configLlmEndpoint'),
      configLlmModel: document.getElementById('configLlmModel'),
      exportFormat: document.getElementById('exportFormat'),
      exportMedia: document.getElementById('exportMedia'),
      exportAnonymize: document.getElementById('exportAnonymize'),
      exportIncremental: document.getElementById('exportIncremental'),
      schedulerMode: document.getElementById('schedulerMode'),
      schedulerInterval: document.getElementById('schedulerInterval'),
      startScheduler: document.getElementById('startScheduler'),
      stopScheduler: document.getElementById('stopScheduler'),
      schedulerStatus: document.getElementById('schedulerStatus'),
      saveConfig: document.getElementById('saveConfig'),
      startExport: document.getElementById('startExport'),
      exportStatus: document.getElementById('exportStatus'),
      exportProgress: document.getElementById('exportProgress')
    };

    const translations = {
      ru: {
        heroSubtitle: 'Загрузите JSON-экспорт и изучайте посты, комментарии, реакции и активность пользователей.',
        uploadJson: 'Загрузить JSON-файл',
        chooseFile: 'Выбор файла',
        noFileSelected: 'Файл не выбран',
        loadingExports: 'Загрузка экспортов...',
        noLocalExports: 'В data/raw нет JSON-экспортов',
        openLocalExport: 'Открыть локальный экспорт',
        sortByDate: 'По дате',
        sortByChannel: 'По каналу',
        localExportsStaticMode: 'Экспорты из data/raw доступны при запуске через сервер.',
        localExportsLoaded: 'Локальных экспортов',
        localExportLoadFailed: 'Не удалось загрузить локальный экспорт',
        nightTheme: 'Ночная тема',
        lightTheme: 'Светлая тема',
        postsPage: 'Страница постов',
        export: 'Экспорт',
        search: 'Поиск',
        searchPlaceholder: 'Текст, post_id, comment_id',
        dateFrom: 'Дата от',
        dateTo: 'Дата до',
        emoji: 'Эмодзи',
        all: 'Все',
        onlyMedia: 'Только с медиа',
        onlyReplies: 'Только ответы',
        file: 'Файл',
        postsCount: 'Постов',
        commentsCount: 'Комментариев',
        uniqueUsers: 'Уникальных пользователей',
        reactionsCount: 'Реакций',
        commentsByDay: 'Комментарии по дням',
        topUsers: 'Топ пользователей',
        topEmoji: 'Топ эмодзи',
        topPosts: 'Самые обсуждаемые посты',
        channelPosts: 'Посты канала',
        date: 'Дата',
        views: 'Просмотры',
        comments: 'Комментарии',
        reactions: 'Реакции',
        media: 'Медиа',
        exportRun: 'Запуск экспорта',
        channel: 'Каналы',
        channelPlaceholder: 'channel, another_channel или https://t.me/channel',
        format: 'Формат',
        postsPauseSeconds: 'Пауза, секунд',
        postsPauseAfterPosts: 'Пауза каждые N постов',
        downloadMedia: 'Скачать медиа',
        anonymization: 'Анонимизация',
        incremental: 'Инкрементально',
        schedulerMode: 'Scheduler mode',
        schedulerInterval: 'Интервал, минут',
        saveEnv: 'Сохранить .env',
        startExport: 'Запустить экспорт',
        startScheduler: 'Запустить scheduler',
        stopScheduler: 'Остановить scheduler',
        schedulerNotStarted: 'Scheduler не запущен',
        schedulerStarting: 'Запуск scheduler...',
        schedulerRunning: 'Scheduler активен',
        schedulerStopped: 'Scheduler остановлен',
        schedulerStartFailed: 'Не удалось запустить scheduler',
        schedulerStopFailed: 'Не удалось остановить scheduler',
        schedulerIntervalRequired: 'Интервал должен быть не меньше 1 минуты',
        nextRun: 'Следующий запуск',
        lastRun: 'Последний запуск',
        skippedRuns: 'Пропущено запусков',
        exportNotStarted: 'Экспорт ещё не запускался.',
        close: 'Закрыть',
        language: 'Язык',
        noData: 'Нет данных',
        rows: 'строк',
        chooseJson: 'Выберите JSON-файл',
        noLoadedData: 'Нет загруженных данных',
        noPostsForFilters: 'Нет постов для выбранных фильтров',
        posts: 'постов',
        collapse: 'Свернуть',
        expand: 'Развернуть',
        openInTg: 'Открыть в TG',
        noText: '[без текста]',
        viewsPill: 'просмотров',
        commentsPill: 'комментариев',
        noComments: 'Комментариев нет',
        openComment: 'Открыть комментарий',
        userComments: 'Комментарии',
        firstComment: 'Первый комментарий',
        lastComment: 'Последний комментарий',
        saveEnvProgress: 'Сохранение .env...',
        saveEnvFailed: 'Не удалось сохранить .env',
        envSaved: '.env сохранён',
        error: 'Ошибка',
        channelRequired: 'Укажите хотя бы один канал',
        starting: 'Запуск...',
        exportStarting: 'Запуск экспорта...',
        exportStartFailed: 'Не удалось запустить экспорт',
        statusError: 'Ошибка статуса',
        noLogs: 'Нет логов',
        exportRunning: 'Экспорт выполняется',
        ready: 'Готово',
        exportDone: 'Экспорт завершён',
        exportFailed: 'Экспорт завершился с ошибкой',
        currentChannel: 'Текущий канал',
        completedChannels: 'Готово',
        failedChannels: 'Ошибки',
        lastError: 'Последняя ошибка',
        openMedia: 'Открыть медиа',
        jsonMustBeArray: 'JSON должен быть массивом постов'
      },
      en: {
        heroSubtitle: 'Upload a JSON export and explore posts, comments, reactions, and user activity.',
        uploadJson: 'Upload JSON file',
        chooseFile: 'Choose file',
        noFileSelected: 'No file selected',
        loadingExports: 'Loading exports...',
        noLocalExports: 'No JSON exports in data/raw',
        openLocalExport: 'Open local export',
        sortByDate: 'By date',
        sortByChannel: 'By channel',
        localExportsStaticMode: 'Server mode loads exports from data/raw.',
        localExportsLoaded: 'Local exports',
        localExportLoadFailed: 'Could not load local export',
        nightTheme: 'Dark theme',
        lightTheme: 'Light theme',
        postsPage: 'Posts page',
        export: 'Export',
        search: 'Search',
        searchPlaceholder: 'Text, post_id, comment_id',
        dateFrom: 'Date from',
        dateTo: 'Date to',
        emoji: 'Emoji',
        all: 'All',
        onlyMedia: 'Only with media',
        onlyReplies: 'Only replies',
        file: 'File',
        postsCount: 'Posts',
        commentsCount: 'Comments',
        uniqueUsers: 'Unique users',
        reactionsCount: 'Reactions',
        commentsByDay: 'Comments by day',
        topUsers: 'Top users',
        topEmoji: 'Top emoji',
        topPosts: 'Most discussed posts',
        channelPosts: 'Channel posts',
        date: 'Date',
        views: 'Views',
        comments: 'Comments',
        reactions: 'Reactions',
        media: 'Media',
        exportRun: 'Run export',
        channel: 'Channels',
        channelPlaceholder: 'channel, another_channel or https://t.me/channel',
        format: 'Format',
        postsPauseSeconds: 'Pause, seconds',
        postsPauseAfterPosts: 'Pause every N posts',
        downloadMedia: 'Download media',
        anonymization: 'Anonymization',
        incremental: 'Incremental',
        schedulerMode: 'Scheduler mode',
        schedulerInterval: 'Interval, minutes',
        saveEnv: 'Save .env',
        startExport: 'Start export',
        startScheduler: 'Start scheduler',
        stopScheduler: 'Stop scheduler',
        schedulerNotStarted: 'Scheduler is not running',
        schedulerStarting: 'Starting scheduler...',
        schedulerRunning: 'Scheduler is active',
        schedulerStopped: 'Scheduler stopped',
        schedulerStartFailed: 'Could not start scheduler',
        schedulerStopFailed: 'Could not stop scheduler',
        schedulerIntervalRequired: 'Interval must be at least 1 minute',
        nextRun: 'Next run',
        lastRun: 'Last run',
        skippedRuns: 'Skipped runs',
        exportNotStarted: 'Export has not started yet.',
        close: 'Close',
        language: 'Language',
        noData: 'No data',
        rows: 'rows',
        chooseJson: 'Choose a JSON file',
        noLoadedData: 'No loaded data',
        noPostsForFilters: 'No posts for selected filters',
        posts: 'posts',
        collapse: 'Collapse',
        expand: 'Expand',
        openInTg: 'Open in TG',
        noText: '[no text]',
        viewsPill: 'views',
        commentsPill: 'comments',
        noComments: 'No comments',
        openComment: 'Open comment',
        userComments: 'Comments',
        firstComment: 'First comment',
        lastComment: 'Last comment',
        saveEnvProgress: 'Saving .env...',
        saveEnvFailed: 'Could not save .env',
        envSaved: '.env saved',
        error: 'Error',
        channelRequired: 'Enter at least one channel',
        starting: 'Starting...',
        exportStarting: 'Starting export...',
        exportStartFailed: 'Could not start export',
        statusError: 'Status error',
        noLogs: 'No logs',
        exportRunning: 'Export is running',
        ready: 'Ready',
        exportDone: 'Export completed',
        exportFailed: 'Export failed with code',
        currentChannel: 'Current channel',
        completedChannels: 'Completed',
        failedChannels: 'Failed',
        lastError: 'Last error',
        openMedia: 'Open media',
        jsonMustBeArray: 'JSON must be an array of posts'
      },
      zh: {
        heroSubtitle: '上传 JSON 导出文件，查看帖子、评论、反应和用户活跃度。',
        uploadJson: '上传 JSON 文件',
        chooseFile: '选择文件',
        noFileSelected: '未选择文件',
        loadingExports: '正在加载导出...',
        noLocalExports: 'data/raw 中没有 JSON 导出',
        openLocalExport: '打开本地导出',
        sortByDate: '按日期',
        sortByChannel: '按频道',
        localExportsStaticMode: '服务器模式会从 data/raw 加载导出。',
        localExportsLoaded: '本地导出',
        localExportLoadFailed: '无法加载本地导出',
        nightTheme: '夜间主题',
        lightTheme: '浅色主题',
        postsPage: '帖子页面',
        export: '导出',
        search: '搜索',
        searchPlaceholder: '文本、post_id、comment_id',
        dateFrom: '开始日期',
        dateTo: '结束日期',
        emoji: '表情',
        all: '全部',
        onlyMedia: '仅含媒体',
        onlyReplies: '仅回复',
        file: '文件',
        postsCount: '帖子',
        commentsCount: '评论',
        uniqueUsers: '唯一用户',
        reactionsCount: '反应',
        commentsByDay: '每日评论',
        topUsers: '热门用户',
        topEmoji: '热门表情',
        topPosts: '讨论最多的帖子',
        channelPosts: '频道帖子',
        date: '日期',
        views: '浏览量',
        comments: '评论',
        reactions: '反应',
        media: '媒体',
        exportRun: '运行导出',
        channel: '频道',
        channelPlaceholder: 'channel, another_channel 或 https://t.me/channel',
        format: '格式',
        postsPauseSeconds: '暂停秒数',
        postsPauseAfterPosts: '每 N 篇帖子暂停',
        downloadMedia: '下载媒体',
        anonymization: '匿名化',
        incremental: '增量',
        schedulerMode: 'Scheduler mode',
        schedulerInterval: '间隔分钟',
        saveEnv: '保存 .env',
        startExport: '开始导出',
        startScheduler: '启动 scheduler',
        stopScheduler: '停止 scheduler',
        schedulerNotStarted: 'Scheduler 未运行',
        schedulerStarting: '正在启动 scheduler...',
        schedulerRunning: 'Scheduler 运行中',
        schedulerStopped: 'Scheduler 已停止',
        schedulerStartFailed: '无法启动 scheduler',
        schedulerStopFailed: '无法停止 scheduler',
        schedulerIntervalRequired: '间隔必须至少为 1 分钟',
        nextRun: '下次运行',
        lastRun: '上次运行',
        skippedRuns: '跳过运行',
        exportNotStarted: '导出尚未开始。',
        close: '关闭',
        language: '语言',
        noData: '没有数据',
        rows: '行',
        chooseJson: '请选择 JSON 文件',
        noLoadedData: '没有已加载数据',
        noPostsForFilters: '没有符合筛选条件的帖子',
        posts: '帖子',
        collapse: '收起',
        expand: '展开',
        openInTg: '在 TG 打开',
        noText: '[无文本]',
        viewsPill: '浏览',
        commentsPill: '评论',
        noComments: '没有评论',
        openComment: '打开评论',
        userComments: '评论',
        firstComment: '第一条评论',
        lastComment: '最后一条评论',
        saveEnvProgress: '正在保存 .env...',
        saveEnvFailed: '无法保存 .env',
        envSaved: '.env 已保存',
        error: '错误',
        channelRequired: '请输入频道',
        starting: '正在启动...',
        exportStarting: '正在启动导出...',
        exportStartFailed: '无法启动导出',
        statusError: '状态错误',
        noLogs: '没有日志',
        exportRunning: '导出运行中',
        ready: '就绪',
        exportDone: '导出完成',
        exportFailed: '导出失败，代码',
        currentChannel: '当前频道',
        completedChannels: '已完成',
        failedChannels: '失败',
        lastError: '最后错误',
        openMedia: '打开媒体',
        jsonMustBeArray: 'JSON 必须是帖子数组'
      }
    };

    initTheme();
    initLanguage();
    el.fileInput.addEventListener('change', handleFile);
    el.localExportSort.addEventListener('change', renderLocalExports);
    el.openLocalExport.addEventListener('click', openSelectedLocalExport);
    el.themeToggle.addEventListener('click', toggleTheme);
    el.languageSelect.addEventListener('change', () => setLanguage(el.languageSelect.value, true));
    el.tabs.forEach((tab) => tab.addEventListener('click', () => setTab(tab.dataset.tab)));
    [el.searchText, el.filterUserId, el.filterUsername, el.filterDateFrom, el.filterDateTo, el.filterEmoji, el.filterMedia, el.filterReplies]
      .forEach((input) => input.addEventListener('input', applyFilters));
    el.postsBody.addEventListener('click', handlePostsClick);
    el.postsBody.addEventListener('keydown', handlePostsKeydown);
    el.closeDrawer.addEventListener('click', closeUserDrawer);
    el.drawerBackdrop.addEventListener('click', closeUserDrawer);
    el.saveConfig.addEventListener('click', saveConfig);
    el.startExport.addEventListener('click', startExport);
    el.startScheduler.addEventListener('click', startScheduler);
    el.stopScheduler.addEventListener('click', stopScheduler);
    el.schedulerMode.addEventListener('change', () => {
      if (!el.schedulerMode.checked && state.schedulerEnabled) {
        stopScheduler();
        return;
      }

      updateSchedulerControls();
    });

    async function handleFile(event) {
      const file = event.target.files[0];

      if (!file) {
        el.selectedFileName.textContent = t('noFileSelected');
        return;
      }

      try {
        const text = await file.text();
        const data = JSON.parse(text);
        loadExportData(file.name, data);
      } catch (error) {
        showLoadError(error);
      }
    }

    function loadExportData(fileName, data) {
      if (!Array.isArray(data)) {
        throw new Error(t('jsonMustBeArray'));
      }

      state.fileName = fileName;
      el.selectedFileName.textContent = fileName;
      el.tableStatus.classList.remove('error');
      parseExport(data);
      populateEmojiFilter();
      applyFilters();
    }

    function showLoadError(error) {
      state.fileName = '';
      el.selectedFileName.textContent = t('noFileSelected');
      resetState();
      el.tableStatus.textContent = `${t('error')}: ${error.message}`;
      el.tableStatus.classList.add('error');
    }

    async function loadLocalExports() {
      try {
        const sortMode = encodeURIComponent(el.localExportSort.value || 'date');
        const response = await fetch(`/api/exports?sort=${sortMode}`, { cache: 'no-store' });

        if (!response.ok) {
          throw new Error(t('localExportLoadFailed'));
        }

        state.localExports = await response.json();
        renderLocalExports();
      } catch (_error) {
        state.localExports = [];
        renderLocalExports();
        el.localExportStatus.textContent = t('localExportsStaticMode');
      }
    }

    function renderLocalExports() {
      const exports = [...state.localExports];
      const sortMode = el.localExportSort.value;

      exports.sort((a, b) => {
        if (sortMode === 'channel') {
          const channelCompare = String(a.channel || '').localeCompare(String(b.channel || ''), undefined, { sensitivity: 'base' });

          if (channelCompare !== 0) {
            return channelCompare;
          }
        }

        return String(b.modified_at || '').localeCompare(String(a.modified_at || ''));
      });

      if (!exports.length) {
        el.localExportSelect.innerHTML = `<option value="">${escapeHtml(t('noLocalExports'))}</option>`;
        el.openLocalExport.disabled = true;
        el.localExportStatus.textContent = t('noLocalExports');
        return;
      }

      el.localExportSelect.innerHTML = exports.map((item) => {
        const label = `${item.channel || '-'} - ${item.file} - ${formatFileSize(item.size_bytes)}`;
        return `<option value="${escapeAttribute(item.file)}">${escapeHtml(label)}</option>`;
      }).join('');
      el.openLocalExport.disabled = false;
      el.localExportStatus.textContent = `${t('localExportsLoaded')}: ${formatNumber(exports.length)}`;
    }

    async function openSelectedLocalExport() {
      const fileName = el.localExportSelect.value;

      if (!fileName) {
        return;
      }

      el.openLocalExport.disabled = true;
      el.localExportStatus.textContent = t('loadingExports');

      try {
        const summaryResponse = await fetch(`/api/export/${encodeURIComponent(fileName)}/summary`, { cache: 'no-store' });
        const summary = await summaryResponse.json();

        if (!summaryResponse.ok || summary.ok === false) {
          throw new Error(summary.error || t('localExportLoadFailed'));
        }

        const response = await fetch(`/data/raw/${encodeURIComponent(fileName)}`, { cache: 'no-store' });

        if (!response.ok) {
          throw new Error(t('localExportLoadFailed'));
        }

        const data = await response.json();
        loadExportData(fileName, data);
        el.localExportStatus.textContent = [
          summary.channel,
          `${formatNumber(summary.posts_count)} ${t('posts')}`,
          `${formatNumber(summary.comments_count)} ${t('comments')}`
        ].filter(Boolean).join(' - ');
      } catch (error) {
        el.localExportStatus.textContent = `${t('error')}: ${error.message}`;
        showLoadError(error);
      } finally {
        el.openLocalExport.disabled = !state.localExports.length;
      }
    }

    function initTheme() {
      const savedTheme = localStorage.getItem('tg-dashboard-theme');
      const initialTheme = savedTheme === 'dark' ? 'dark' : 'light';
      applyTheme(initialTheme);
    }

    function toggleTheme() {
      const nextTheme = document.body.dataset.theme === 'dark' ? 'light' : 'dark';
      applyTheme(nextTheme);
      localStorage.setItem('tg-dashboard-theme', nextTheme);
    }

    function applyTheme(theme) {
      const isDark = theme === 'dark';
      document.body.dataset.theme = isDark ? 'dark' : 'light';
      el.themeToggle.textContent = isDark ? t('lightTheme') : t('nightTheme');
      el.themeToggle.setAttribute('aria-pressed', isDark ? 'true' : 'false');
    }

    function initLanguage() {
      const savedLanguage = localStorage.getItem('tg-dashboard-language');
      const initialLanguage = translations[savedLanguage] ? savedLanguage : 'ru';
      setLanguage(initialLanguage, false);
    }

    function setLanguage(language, persist) {
      state.language = translations[language] ? language : 'ru';
      el.languageSelect.value = state.language;

      if (persist) {
        localStorage.setItem('tg-dashboard-language', state.language);
      }

      applyLanguage();
    }

    function t(key) {
      return (translations[state.language] && translations[state.language][key])
        || translations.ru[key]
        || key;
    }

    function applyLanguage() {
      document.documentElement.lang = state.language === 'zh' ? 'zh' : state.language;

      document.querySelectorAll('[data-i18n]').forEach((node) => {
        node.textContent = t(node.dataset.i18n);
      });

      document.querySelectorAll('[data-i18n-placeholder]').forEach((node) => {
        node.setAttribute('placeholder', t(node.dataset.i18nPlaceholder));
      });

      applyTheme(document.body.dataset.theme === 'dark' ? 'dark' : 'light');

      if (!state.fileName) {
        el.selectedFileName.textContent = t('noFileSelected');
        el.tableStatus.textContent = t('chooseJson');
        el.daysStatus.textContent = t('noData');
        el.usersStatus.textContent = t('noData');
        el.emojiStatus.textContent = t('noData');
        el.postsStatus.textContent = t('noData');
      } else {
        el.selectedFileName.textContent = state.fileName;
      }

      if (!el.exportProgress.dataset.touched) {
        el.exportProgress.textContent = t('exportNotStarted');
      }

      renderAll();
      populateEmojiFilter();
      renderLocalExports();
      updateSchedulerControls();
    }

    function parseExport(rawPosts) {
      resetState();
      state.rawPosts = rawPosts;
      state.posts = rawPosts.map(normalizePost);
      state.comments = state.posts.flatMap((post) => post.comments);
      buildUsers();
    }

    function normalizePost(post) {
      const comments = Array.isArray(post.comments) ? post.comments : [];
      const normalizedPost = {
        id: String(post.post_id ?? ''),
        date: post.post_date || '',
        text: post.post_text || '',
        views: post.post_views ?? '',
        forwards: post.post_forwards ?? '',
        link: post.post_link || '',
        mediaPath: post.post_media || '',
        reactions: Array.isArray(post.post_reactions) ? post.post_reactions : [],
        hasMedia: detectMedia(post),
        raw: post,
        comments: []
      };

      normalizedPost.comments = comments.map((comment) => normalizeComment(comment, normalizedPost));
      return normalizedPost;
    }

    function normalizeComment(comment, post) {
      const user = comment.user || null;

      return {
        id: String(comment.comment_id ?? ''),
        date: comment.comment_date || '',
        text: comment.comment_text || '',
        link: comment.comment_link || '',
        mediaPath: comment.comment_media || '',
        replyTo: comment.reply_to_msg_id == null ? '' : String(comment.reply_to_msg_id),
        reactions: Array.isArray(comment.comment_reactions) ? comment.comment_reactions : [],
        user,
        userId: user && user.user_id != null ? String(user.user_id) : '',
        username: user && user.username ? String(user.username) : '',
        fullName: formatUserName(user),
        postId: post.id,
        postDate: post.date,
        postText: post.text,
        postHasMedia: post.hasMedia,
        hasMedia: Boolean(comment.comment_media || comment.media || comment.photo || comment.video || comment.document),
        raw: comment
      };
    }

    function buildUsers() {
      state.users = new Map();

      for (const comment of state.comments) {
        if (!comment.userId) {
          continue;
        }

        const current = state.users.get(comment.userId) || {
          id: comment.userId,
          username: comment.username,
          fullName: comment.fullName,
          user: comment.user,
          comments: []
        };

        current.username = current.username || comment.username;
        current.fullName = current.fullName || comment.fullName;
        current.comments.push(comment);
        state.users.set(comment.userId, current);
      }
    }

    function applyFilters() {
      const filters = getFilters();

      state.filteredComments = state.comments.filter((comment) => commentMatchesFilters(comment, filters));
      const allowedPostIds = new Set(state.filteredComments.map((comment) => comment.postId));

      state.filteredPosts = state.posts.filter((post) => {
        const postTextMatch = !filters.search || [
          post.id,
          post.text,
          post.date
        ].join(' ').toLowerCase().includes(filters.search);

        const postDateMatch = dateInRange(post.date, filters.dateFrom, filters.dateTo);
        const postEmojiMatch = !filters.emoji || post.reactions.some((reaction) => reaction.emoji === filters.emoji);
        const postMediaMatch = !filters.onlyMedia || post.hasMedia;

        if (filters.userId || filters.username || filters.onlyReplies) {
          return allowedPostIds.has(post.id);
        }

        return postTextMatch && postDateMatch && postEmojiMatch && postMediaMatch;
      });

      renderAll();
    }

    function getFilters() {
      return {
        search: el.searchText.value.trim().toLowerCase(),
        userId: el.filterUserId.value.trim().toLowerCase(),
        username: el.filterUsername.value.trim().toLowerCase().replace(/^@/, ''),
        dateFrom: el.filterDateFrom.value,
        dateTo: el.filterDateTo.value,
        emoji: el.filterEmoji.value,
        onlyMedia: el.filterMedia.checked,
        onlyReplies: el.filterReplies.checked
      };
    }

    function commentMatchesFilters(comment, filters) {
      const searchText = [
        comment.id,
        comment.text,
        comment.postId,
        comment.postText,
        comment.fullName,
        comment.username,
        comment.userId
      ].join(' ').toLowerCase();

      if (filters.search && !searchText.includes(filters.search)) {
        return false;
      }

      if (filters.userId && !comment.userId.toLowerCase().includes(filters.userId)) {
        return false;
      }

      if (filters.username && !comment.username.toLowerCase().includes(filters.username)) {
        return false;
      }

      if (!dateInRange(comment.date || comment.postDate, filters.dateFrom, filters.dateTo)) {
        return false;
      }

      if (filters.emoji && !comment.reactions.some((reaction) => reaction.emoji === filters.emoji)) {
        const post = state.posts.find((item) => item.id === comment.postId);
        if (!post || !post.reactions.some((reaction) => reaction.emoji === filters.emoji)) {
          return false;
        }
      }

      if (filters.onlyMedia && !comment.postHasMedia && !comment.hasMedia) {
        return false;
      }

      if (filters.onlyReplies && !isReply(comment)) {
        return false;
      }

      return true;
    }

    function renderAll() {
      renderSummary();
      renderCharts();
      renderPostsTable();
    }

    function renderSummary() {
      const filteredUserIds = new Set(state.filteredComments.map((comment) => comment.userId).filter(Boolean));
      el.metricFile.textContent = state.fileName || '-';
      el.metricPosts.textContent = formatNumber(state.filteredPosts.length);
      el.metricComments.textContent = formatNumber(state.filteredComments.length);
      el.metricUsers.textContent = formatNumber(filteredUserIds.size);
      el.metricReactions.textContent = formatNumber(countReactions(state.filteredPosts, state.filteredComments));
    }

    function renderCharts() {
      const byDay = countBy(state.filteredComments, (comment) => formatDay(comment.date));
      const topUsers = Array.from(groupCommentsByUser(state.filteredComments).values())
        .map((user) => ({ label: user.fullName, value: user.comments.length, userId: user.id }))
        .sort((a, b) => b.value - a.value)
        .slice(0, 10);
      const topEmoji = getTopEmoji(state.filteredPosts, state.filteredComments).slice(0, 10);
      const topPosts = state.filteredPosts
        .map((post) => ({ label: `Post ${post.id}`, value: post.comments.filter((comment) => state.filteredComments.includes(comment)).length, postId: post.id }))
        .filter((item) => item.value > 0)
        .sort((a, b) => b.value - a.value)
        .slice(0, 10);

      renderBarChart(el.commentsByDayChart, Object.entries(byDay).map(([label, value]) => ({ label, value })), el.daysStatus);
      renderBarChart(el.topUsersChart, topUsers, el.usersStatus, (item) => openUserDrawer(item.userId));
      renderBarChart(el.topEmojiChart, topEmoji, el.emojiStatus);
      renderBarChart(el.topPostsChart, topPosts, el.postsStatus, (item) => {
        state.expandedPostId = item.postId;
        setTab('posts');
        renderPostsTable();
      });
    }

    function renderBarChart(container, data, statusElement, onClick) {
      if (!data.length) {
        container.innerHTML = `<div class="empty">${escapeHtml(t('noData'))}</div>`;
        statusElement.textContent = '0';
        return;
      }

      const max = Math.max(...data.map((item) => item.value), 1);
      statusElement.textContent = `${formatNumber(data.length)} ${t('rows')}`;
      container.innerHTML = data.map((item) => {
        const width = Math.max(3, (item.value / max) * 100);
        const buttonAttrs = onClick ? `type="button" data-chart-label="${escapeAttribute(item.label)}"` : '';
        const label = onClick
          ? `<button class="user-link chart-action" ${buttonAttrs}>${escapeHtml(item.label)}</button>`
          : `<span>${escapeHtml(item.label)}</span>`;

        return `
          <div class="bar-row">
            <div class="bar-label">${label}</div>
            <div class="bar-track"><div class="bar-fill" style="width: ${width}%"></div></div>
            <div class="bar-value">${formatNumber(item.value)}</div>
          </div>
        `;
      }).join('');

      if (onClick) {
        container.querySelectorAll('.chart-action').forEach((button, index) => {
          button.addEventListener('click', () => onClick(data[index]));
        });
      }
    }

    function renderPostsTable() {
      el.tableStatus.classList.remove('error');
      el.tableStatus.textContent = state.fileName
        ? `${formatNumber(state.filteredPosts.length)} ${t('posts')}`
        : t('chooseJson');

      if (!state.filteredPosts.length) {
        const emptyMessage = state.fileName ? t('noPostsForFilters') : t('noLoadedData');
        el.postsBody.innerHTML = `<tr><td colspan="6" class="empty">${escapeHtml(emptyMessage)}</td></tr>`;
        return;
      }

      el.postsBody.innerHTML = state.filteredPosts.map((post) => {
        const filteredComments = post.comments.filter((comment) => state.filteredComments.includes(comment));
        const isExpanded = state.expandedPostId === post.id;
        const reactionsCount = sumReactions(post.reactions);

        return `
          <tr class="post-row ${isExpanded ? 'expanded' : ''}" data-post-id="${escapeAttribute(post.id)}" tabindex="0" aria-expanded="${isExpanded ? 'true' : 'false'}">
            <td>
              <span class="post-title">Post ${escapeHtml(post.id)}</span>
              <span class="row-action">${isExpanded ? escapeHtml(t('collapse')) : escapeHtml(t('expand'))}</span>
              ${renderTelegramLink(post.link, t('openInTg'))}
              ${renderMedia(post.mediaPath)}
              <div class="text-preview">${escapeHtml(post.text || t('noText'))}</div>
            </td>
            <td>${escapeHtml(formatDate(post.date))}</td>
            <td>${formatNumber(post.views || 0)}</td>
            <td>${formatNumber(filteredComments.length)}</td>
            <td>${formatReactionList(post.reactions)}</td>
            <td>${post.hasMedia ? '<span class="pill">media</span>' : '-'}</td>
          </tr>
          ${isExpanded ? renderPostDetail(post, filteredComments) : ''}
        `;
      }).join('');
    }

    function renderPostDetail(post, comments) {
      return `
        <tr>
          <td colspan="6">
            <div class="post-detail">
              <div class="post-full-text">${escapeHtml(post.text || t('noText'))}</div>
              ${renderMedia(post.mediaPath)}
              <div>
                <span class="pill">post ${escapeHtml(post.id)}</span>
                <span class="pill">${escapeHtml(formatDate(post.date))}</span>
                <span class="pill">${formatNumber(post.views || 0)} ${escapeHtml(t('viewsPill'))}</span>
                <span class="pill">${formatNumber(comments.length)} ${escapeHtml(t('commentsPill'))}</span>
                ${renderTelegramLink(post.link, t('openInTg'))}
              </div>
              <div class="comment-tree">
                ${renderCommentTree(comments)}
              </div>
            </div>
          </td>
        </tr>
      `;
    }

    function renderCommentTree(comments) {
      if (!comments.length) {
        return `<div class="empty">${escapeHtml(t('noComments'))}</div>`;
      }

      const byId = new Map(comments.map((comment) => [comment.id, { ...comment, children: [] }]));
      const roots = [];

      for (const node of byId.values()) {
        const parent = byId.get(node.replyTo);

        if (parent && parent.id !== node.id) {
          parent.children.push(node);
        } else {
          roots.push(node);
        }
      }

      const sortByDate = (a, b) => getTimestamp(a.date) - getTimestamp(b.date);
      roots.sort(sortByDate);
      byId.forEach((node) => node.children.sort(sortByDate));

      return roots.map((node) => renderCommentNode(node, 0)).join('');
    }

    function renderCommentNode(comment, depth) {
      const depthClass = `depth-${Math.min(depth, 4)}`;
      const userButton = comment.userId
        ? `<button class="user-link" type="button" data-user-id="${escapeAttribute(comment.userId)}">${escapeHtml(comment.fullName)}</button>`
        : '<span>Unknown user</span>';
      const replyLabel = comment.replyTo ? `<span class="pill">reply to ${escapeHtml(comment.replyTo)}</span>` : '';

      return `
        <div class="comment-node ${depthClass}">
          <div class="comment-meta">
            ${userButton}
            <span>${escapeHtml(formatDate(comment.date))}</span>
            <span class="pill">comment ${escapeHtml(comment.id)}</span>
            ${replyLabel}
            ${formatReactionList(comment.reactions)}
            ${renderTelegramLink(comment.link, t('openComment'))}
          </div>
          ${renderMedia(comment.mediaPath)}
          <div class="comment-text">${escapeHtml(comment.text || t('noText'))}</div>
        </div>
        ${comment.children.map((child) => renderCommentNode(child, depth + 1)).join('')}
      `;
    }

    function handlePostsClick(event) {
      const userButton = event.target.closest('[data-user-id]');
      const postRow = event.target.closest('.post-row');

      if (userButton) {
        openUserDrawer(userButton.dataset.userId);
        return;
      }

      if (!postRow || event.target.closest('a, button, input, select, textarea')) {
        return;
      }

      togglePostRow(postRow.dataset.postId);
    }

    function handlePostsKeydown(event) {
      if (event.key !== 'Enter' && event.key !== ' ') {
        return;
      }

      const postRow = event.target.closest('.post-row');

      if (!postRow) {
        return;
      }

      event.preventDefault();
      togglePostRow(postRow.dataset.postId);
    }

    function togglePostRow(postId) {
      state.expandedPostId = state.expandedPostId === postId ? null : postId;
      renderPostsTable();
    }

    function openUserDrawer(userId) {
      const user = groupCommentsByUser(state.comments).get(userId);

      if (!user) {
        return;
      }

      const comments = [...user.comments].sort((a, b) => getTimestamp(a.date) - getTimestamp(b.date));
      const first = comments[0];
      const last = comments[comments.length - 1];

      el.drawerUserName.textContent = user.fullName || 'User';
      el.drawerUserMeta.textContent = `Id: ${user.id}${user.username ? ` · @${user.username}` : ''}`;
      el.drawerBody.innerHTML = `
        <div class="user-stats">
          <div class="user-stat"><span>User</span><strong>${escapeHtml(user.fullName || '-')}</strong></div>
          <div class="user-stat"><span>Id</span><strong>${escapeHtml(user.id)}</strong></div>
          <div class="user-stat"><span>${escapeHtml(t('userComments'))}</span><strong>${formatNumber(comments.length)}</strong></div>
          <div class="user-stat"><span>Username</span><strong>${escapeHtml(user.username ? `@${user.username}` : '-')}</strong></div>
          <div class="user-stat"><span>${escapeHtml(t('firstComment'))}</span><strong>${escapeHtml(formatDate(first && first.date))}</strong></div>
          <div class="user-stat"><span>${escapeHtml(t('lastComment'))}</span><strong>${escapeHtml(formatDate(last && last.date))}</strong></div>
        </div>
        <div class="comment-tree">
          ${comments.map((comment) => `
            <div class="comment-node">
              <div class="comment-meta">
                <span>${escapeHtml(formatDate(comment.date))}</span>
                <button class="post-title" type="button" data-drawer-post-id="${escapeAttribute(comment.postId)}">Post ${escapeHtml(comment.postId)}</button>
                <span class="pill">comment ${escapeHtml(comment.id)}</span>
                ${renderTelegramLink(comment.link, t('openComment'))}
              </div>
              ${renderMedia(comment.mediaPath)}
              <div class="comment-text">${escapeHtml(comment.text || t('noText'))}</div>
            </div>
          `).join('')}
        </div>
      `;

      el.drawerBody.querySelectorAll('[data-drawer-post-id]').forEach((button) => {
        button.addEventListener('click', () => {
          state.expandedPostId = button.dataset.drawerPostId;
          closeUserDrawer();
          setTab('posts');
          renderPostsTable();
        });
      });

      el.drawerBackdrop.classList.add('open');
      el.userDrawer.classList.add('open');
    }

    function closeUserDrawer() {
      el.drawerBackdrop.classList.remove('open');
      el.userDrawer.classList.remove('open');
    }

    function setTab(tabName) {
      state.activeTab = tabName;
      el.tabs.forEach((tab) => tab.classList.toggle('active', tab.dataset.tab === tabName));
      el.dashboardView.classList.toggle('active', tabName === 'dashboard');
      el.postsView.classList.toggle('active', tabName === 'posts');
      el.exportView.classList.toggle('active', tabName === 'export');
    }

    const configFields = {
      API_ID: el.configApiId,
      API_HASH: el.configApiHash,
      CHANNEL: el.exportChannel,
      TELEGRAM_SESSION: el.configTelegramSession,
      OUTPUT_FILE: el.configOutputFile,
      POST_LIMIT: el.configPostLimit,
      INCREMENTAL_LOOKBACK_POSTS: el.configIncrementalLookbackPosts,
      POSTS_PAUSE_SECONDS: el.configPostsPauseSeconds,
      POSTS_PAUSE_AFTER_POSTS: el.configPostsPauseAfterPosts,
      POSTGRES_HOST: el.configPostgresHost,
      POSTGRES_PORT: el.configPostgresPort,
      POSTGRES_DB: el.configPostgresDb,
      POSTGRES_USER: el.configPostgresUser,
      POSTGRES_PASSWORD: el.configPostgresPassword,
      POSTGRES_TABLE: el.configPostgresTable,
      LLM_ENDPOINT: el.configLlmEndpoint,
      LLM_MODEL: el.configLlmModel
    };

    async function loadServerConfig() {
      try {
        const response = await fetch('/api/config', { cache: 'no-store' });

        if (!response.ok) {
          return;
        }

        const data = await response.json();

        fillConfigForm(data);
      } catch (_error) {
        // Static file mode: API is not available.
      }
    }

    async function loadAppVersion() {
      try {
        const response = await fetch('/api/version', { cache: 'no-store' });

        if (!response.ok) {
          return;
        }

        const data = await response.json();

        if (data.version) {
          el.appVersion.textContent = `v${data.version}`;
        }
      } catch (_error) {
        el.appVersion.textContent = 'v2.1.0';
      }
    }

    function fillConfigForm(config) {
      Object.entries(configFields).forEach(([key, input]) => {
        if (input && Object.prototype.hasOwnProperty.call(config, key)) {
          input.value = config[key] || '';
        }
      });
    }

    function collectConfigForm() {
      const config = {};

      Object.entries(configFields).forEach(([key, input]) => {
        if (input) {
          config[key] = input.value.trim();
        }
      });

      return config;
    }

    async function saveConfig() {
      el.saveConfig.disabled = true;
      el.exportStatus.textContent = t('saveEnvProgress');

      try {
        const response = await fetch('/api/config', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify(collectConfigForm())
        });
        const data = await response.json();

        if (!response.ok || !data.ok) {
          throw new Error(data.error || t('saveEnvFailed'));
        }

        fillConfigForm(data.config || {});
        el.exportStatus.textContent = t('envSaved');
      } catch (error) {
        el.exportStatus.textContent = `${t('error')}: ${error.message}`;
      } finally {
        el.saveConfig.disabled = false;
      }
    }

    function buildExportPayload() {
      return {
        channel: el.exportChannel.value.trim(),
        format: el.exportFormat.value,
        download_media: el.exportMedia.checked,
        anonymize: el.exportAnonymize.checked,
        incremental: el.exportIncremental.checked,
        config: collectConfigForm()
      };
    }

    async function startExport() {
      const payload = buildExportPayload();

      if (!payload.channel) {
        el.exportStatus.textContent = t('channelRequired');
        return;
      }

      el.startExport.disabled = true;
      el.exportStatus.textContent = t('starting');
      el.exportProgress.textContent = t('exportStarting');
      el.exportProgress.dataset.touched = 'true';

      try {
        const response = await fetch('/api/export/start', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify(payload)
        });
        const data = await response.json();

        if (!response.ok || !data.ok) {
          throw new Error(data.error || t('exportStartFailed'));
        }

        pollExportStatus();
      } catch (error) {
        el.exportStatus.textContent = `${t('error')}: ${error.message}`;
        el.startExport.disabled = false;
      }
    }

    async function startScheduler() {
      const payload = {
        ...buildExportPayload(),
        interval_minutes: Number(el.schedulerInterval.value)
      };

      if (!payload.channel) {
        el.schedulerStatus.textContent = t('channelRequired');
        return;
      }

      if (!payload.interval_minutes || payload.interval_minutes < 1) {
        el.schedulerStatus.textContent = t('schedulerIntervalRequired');
        return;
      }

      updateSchedulerControls();
      el.schedulerStatus.textContent = t('schedulerStarting');

      try {
        const response = await fetch('/api/scheduler/start', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify(payload)
        });
        const data = await response.json();

        if (!response.ok || !data.ok) {
          throw new Error(data.error || t('schedulerStartFailed'));
        }

        renderSchedulerStatus(data.scheduler || {});
        pollExportStatus();
        pollSchedulerStatus();
      } catch (error) {
        el.schedulerStatus.textContent = `${t('error')}: ${error.message}`;
        el.schedulerMode.checked = false;
        updateSchedulerControls();
      }
    }

    async function stopScheduler() {
      el.stopScheduler.disabled = true;

      try {
        const response = await fetch('/api/scheduler/stop', {
          method: 'POST'
        });
        const data = await response.json();

        if (!response.ok || !data.ok) {
          throw new Error(data.error || t('schedulerStopFailed'));
        }

        renderSchedulerStatus(data.scheduler || {});
      } catch (error) {
        el.schedulerStatus.textContent = `${t('error')}: ${error.message}`;
      } finally {
        updateSchedulerControls();
      }
    }

    async function pollSchedulerStatus() {
      try {
        const response = await fetch('/api/scheduler/status', { cache: 'no-store' });

        if (!response.ok) {
          return;
        }

        const data = await response.json();
        renderSchedulerStatus(data);

        if (data.enabled) {
          window.setTimeout(pollSchedulerStatus, 5000);
        }
      } catch (_error) {
        el.schedulerStatus.textContent = t('schedulerNotStarted');
      }
    }

    function renderSchedulerStatus(data) {
      const enabled = Boolean(data.enabled);
      const parts = [];

      state.schedulerEnabled = enabled;
      el.schedulerMode.checked = enabled;

      if (!enabled) {
        el.schedulerStatus.textContent = t('schedulerNotStarted');
        updateSchedulerControls();
        return;
      }

      if (data.interval_minutes) {
        el.schedulerInterval.value = data.interval_minutes;
      }

      parts.push(`${t('schedulerRunning')}: ${data.channels || '-'}`);
      parts.push(`${t('nextRun')}: ${formatDateTimeValue(data.next_run_at)}`);

      if (data.last_run_at) {
        parts.push(`${t('lastRun')}: ${formatDateTimeValue(data.last_run_at)}`);
      }

      if (data.runs_skipped) {
        parts.push(`${t('skippedRuns')}: ${formatNumber(data.runs_skipped)}`);
      }

      if (data.last_error) {
        parts.push(`${t('error')}: ${data.last_error}`);
      }

      el.schedulerStatus.textContent = parts.join(' | ');
      updateSchedulerControls();
    }

    function updateSchedulerControls() {
      const enabled = state.schedulerEnabled;
      el.schedulerInterval.disabled = enabled;
      el.startScheduler.disabled = enabled;
      el.stopScheduler.disabled = !enabled;
    }

    async function pollExportStatus() {
      try {
        const response = await fetch('/api/export/status', { cache: 'no-store' });
        const data = await response.json();
        renderExportStatus(data);

        if (data.running) {
          window.setTimeout(pollExportStatus, 1500);
        }
      } catch (error) {
        el.exportStatus.textContent = `${t('statusError')}: ${error.message}`;
        el.startExport.disabled = false;
      }
    }

    function renderExportStatus(data) {
      const lines = data.lines || [];
      const statusDetails = formatExportStatusDetails(data);
      const progressLines = statusDetails.length ? statusDetails.concat(lines) : lines;
      el.exportProgress.textContent = progressLines.length ? progressLines.join('\n') : t('noLogs');
      el.exportProgress.scrollTop = el.exportProgress.scrollHeight;

      if (data.running) {
        el.exportStatus.textContent = t('exportRunning');
        el.startExport.disabled = true;
        return;
      }

      if (data.returncode === null || data.returncode === undefined) {
        el.exportStatus.textContent = t('ready');
      } else if (data.returncode === 0) {
        el.exportStatus.textContent = t('exportDone');
        loadLocalExports();
      } else {
        el.exportStatus.textContent = `${t('exportFailed')} ${data.returncode}`;
      }

      el.startExport.disabled = false;
    }

    function formatExportStatusDetails(data) {
      const details = [];

      if (data.current_channel) {
        details.push(`${t('currentChannel')}: ${data.current_channel}`);
      }

      if ((data.completed_channels || []).length) {
        details.push(`${t('completedChannels')}: ${data.completed_channels.join(', ')}`);
      }

      if ((data.failed_channels || []).length) {
        details.push(`${t('failedChannels')}: ${data.failed_channels.join(', ')}`);
      }

      if (data.last_error) {
        details.push(`${t('lastError')}: ${data.last_error}`);
      }

      if (details.length) {
        details.push('');
      }

      return details;
    }

    function populateEmojiFilter() {
      const emojis = getTopEmoji(state.posts, state.comments).map((item) => item.label);
      el.filterEmoji.innerHTML = `<option value="">${escapeHtml(t('all'))}</option>` + emojis
        .map((emoji) => `<option value="${escapeAttribute(emoji)}">${escapeHtml(emoji)}</option>`)
        .join('');
    }

    function groupCommentsByUser(comments) {
      const users = new Map();

      for (const comment of comments) {
        if (!comment.userId) {
          continue;
        }

        const current = users.get(comment.userId) || {
          id: comment.userId,
          username: comment.username,
          fullName: comment.fullName,
          comments: []
        };

        current.username = current.username || comment.username;
        current.fullName = current.fullName || comment.fullName;
        current.comments.push(comment);
        users.set(comment.userId, current);
      }

      return users;
    }

    function getTopEmoji(posts, comments) {
      const totals = new Map();

      for (const post of posts) {
        for (const reaction of post.reactions) {
          addEmoji(totals, reaction);
        }
      }

      for (const comment of comments) {
        for (const reaction of comment.reactions) {
          addEmoji(totals, reaction);
        }
      }

      return Array.from(totals.entries())
        .map(([label, value]) => ({ label, value }))
        .sort((a, b) => b.value - a.value);
    }

    function addEmoji(totals, reaction) {
      const emoji = reaction && reaction.emoji;
      const count = Number(reaction && reaction.count) || 0;

      if (!emoji) {
        return;
      }

      totals.set(emoji, (totals.get(emoji) || 0) + count);
    }

    function countBy(items, getKey) {
      return items.reduce((acc, item) => {
        const key = getKey(item) || '-';
        acc[key] = (acc[key] || 0) + 1;
        return acc;
      }, {});
    }

    function countReactions(posts, comments) {
      return posts.reduce((sum, post) => sum + sumReactions(post.reactions), 0)
        + comments.reduce((sum, comment) => sum + sumReactions(comment.reactions), 0);
    }

    function sumReactions(reactions) {
      return (reactions || []).reduce((sum, reaction) => sum + (Number(reaction.count) || 0), 0);
    }

    function formatReactionList(reactions) {
      if (!reactions || !reactions.length) {
        return '-';
      }

      return reactions
        .map((reaction) => `<span class="pill">${escapeHtml(reaction.emoji || '?')} ${formatNumber(reaction.count || 0)}</span>`)
        .join(' ');
    }

    function renderTelegramLink(link, label) {
      if (!link) {
        return '';
      }

      return `<a class="telegram-link" href="${escapeAttribute(link)}" target="_blank" rel="noopener noreferrer">${escapeHtml(label)}</a>`;
    }

    function renderMedia(path) {
      const url = normalizeMediaUrl(path);

      if (!url) {
        return '';
      }

      const kind = getMediaKind(url);
      const safeUrl = escapeAttribute(url);

      if (kind === 'image') {
        return `<div class="media-preview"><img src="${safeUrl}" alt="media" loading="lazy"></div>`;
      }

      if (kind === 'video') {
        return `<div class="media-preview"><video src="${safeUrl}" controls preload="metadata"></video></div>`;
      }

      if (kind === 'audio') {
        return `<div class="media-preview"><audio src="${safeUrl}" controls preload="metadata"></audio></div>`;
      }

      return `<div class="media-preview"><a class="telegram-link" href="${safeUrl}" target="_blank" rel="noopener noreferrer">${escapeHtml(t('openMedia'))}</a></div>`;
    }

    function normalizeMediaUrl(path) {
      if (!path) {
        return '';
      }

      let value = String(path).replace(/\\/g, '/');

      if (/^(https?:|data:|blob:)/i.test(value)) {
        return value;
      }

      const marker = 'data/content/';
      const markerIndex = value.indexOf(marker);

      if (markerIndex >= 0) {
        return value.slice(markerIndex);
      }

      const fileName = state.fileName ? state.fileName.replace(/\.json$/i, '') : '';

      if (fileName && !value.includes('/')) {
        return `data/content/${fileName}/${value}`;
      }

      return value.replace(/^\/+/, '');
    }

    function getMediaKind(url) {
      const cleanUrl = url.split('?')[0].toLowerCase();

      if (/\.(jpg|jpeg|png|gif|webp|bmp|svg)$/.test(cleanUrl)) {
        return 'image';
      }

      if (/\.(mp4|webm|mov|m4v|avi|mkv)$/.test(cleanUrl)) {
        return 'video';
      }

      if (/\.(mp3|wav|ogg|m4a|aac|flac)$/.test(cleanUrl)) {
        return 'audio';
      }

      return 'file';
    }

    function detectMedia(post) {
      if (post.has_media || post.post_has_media || post.media || post.post_media || post.post_media_path || post.post_media_file || post.photo || post.video || post.document) {
        return true;
      }

      return /https?:\/\/|t\.me\/|youtu\.be|youtube\.com|twitch\.tv|\.jpg|\.jpeg|\.png|\.gif|\.mp4/i.test(post.post_text || '');
    }

    function isReply(comment) {
      if (!comment.replyTo) {
        return false;
      }

      const post = state.posts.find((item) => item.id === comment.postId);
      return Boolean(post && post.comments.some((item) => item.id === comment.replyTo));
    }

    function dateInRange(value, from, to) {
      const timestamp = getTimestamp(value);

      if (!timestamp) {
        return true;
      }

      if (from && timestamp < new Date(`${from}T00:00:00`).getTime()) {
        return false;
      }

      if (to && timestamp > new Date(`${to}T23:59:59`).getTime()) {
        return false;
      }

      return true;
    }

    function formatUserName(user) {
      if (!user) {
        return 'Unknown user';
      }

      const name = [user.first_name, user.last_name].filter(Boolean).join(' ').trim();
      return name || (user.username ? `@${user.username}` : `User ${user.user_id}`);
    }

    function formatDay(value) {
      const date = new Date(value);

      if (Number.isNaN(date.getTime())) {
        return '-';
      }

      return date.toISOString().slice(0, 10);
    }

    function formatDate(value) {
      if (!value) {
        return '';
      }

      const date = new Date(value);

      if (Number.isNaN(date.getTime())) {
        return value;
      }

      return new Intl.DateTimeFormat('ru-RU', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
      }).format(date);
    }

    function formatDateTimeValue(value) {
      if (!value) {
        return '-';
      }

      const date = new Date(Number(value) * 1000);

      if (Number.isNaN(date.getTime())) {
        return '-';
      }

      return new Intl.DateTimeFormat('ru-RU', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
      }).format(date);
    }

    function getTimestamp(value) {
      const date = new Date(value);
      return Number.isNaN(date.getTime()) ? 0 : date.getTime();
    }

    function formatNumber(value) {
      return new Intl.NumberFormat('ru-RU').format(Number(value) || 0);
    }

    function formatFileSize(bytes) {
      const value = Number(bytes) || 0;

      if (value < 1024) {
        return `${value} B`;
      }

      if (value < 1024 * 1024) {
        return `${(value / 1024).toFixed(1)} KB`;
      }

      return `${(value / 1024 / 1024).toFixed(1)} MB`;
    }

    function resetState() {
      state.rawPosts = [];
      state.posts = [];
      state.filteredPosts = [];
      state.comments = [];
      state.filteredComments = [];
      state.users = new Map();
      state.expandedPostId = null;
      renderAll();
    }

    function escapeHtml(value) {
      return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
    }

    function escapeAttribute(value) {
      return escapeHtml(value).replace(/`/g, '&#096;');
    }

    renderAll();
    updateSchedulerControls();
    loadAppVersion();
    loadServerConfig();
    loadLocalExports();
    pollExportStatus();
    pollSchedulerStatus();
