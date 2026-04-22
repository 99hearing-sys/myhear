/**
 * ===================================================================
 * MyHear 24 · AI 상담 챗봇 (프론트엔드)
 * ===================================================================
 * 
 * 배포:
 *   1) 이 파일을 GitHub 저장소 루트(index.html과 같은 폴더)에 업로드
 *   2) 아래 WORKER_URL을 본인 Cloudflare Worker URL로 교체
 *   3) index.html에 <script src="/myhear24-chatbot.js" defer></script> 한 줄 추가
 * 
 * 보안:
 *   - 이 파일엔 API 키 없음. 모든 API 호출은 Cloudflare Worker 경유.
 *   - auto_update.py가 index.html을 매일 수정해도 이 파일은 독립.
 * 
 * 기능:
 *   - 우측 하단 플로팅 "My 24" 버튼 (파동 애니메이션)
 *   - 클릭 시 풀스크린 모달 (모바일) / 우측 사이드 모달 (데스크톱)
 *   - 웹 음성 인식 (Web Speech API, 한국어)
 *   - 시니어 친화 (큰 글씨, 자주 묻는 질문 6개)
 *   - AI 정체성 명확 (사람 행세 금지)
 * ===================================================================
 */

(function() {
  'use strict';

  // ⭐⭐⭐ 여기를 본인 Cloudflare Worker URL로 교체 ⭐⭐⭐
  const WORKER_URL = 'https://myhear-chat-api.99hearing.workers.dev';
  // ────────────────────────────────────────────────────────

  const QUICK_PROMPTS = [
    '잘 안 들리는데 보청기 해야 할까요?',
    '70대 어머니 보청기 알아보고 있어요',
    '보청기 가격이 너무 다양해요. 차이가 뭔가요?',
    '131만원 보조금 받을 수 있나요?',
    '귓속형이 작아서 좋다는데 단점 있어요?',
    '직접 검사받으려면 어디로 가야 해요?'
  ];

  const INITIAL_GREETING = '안녕하세요. 저는 MyHear 24입니다.\n\n보청기 에디터(청각학 15년 차, 99유럽보청기 운영)가 만들고 학습시킨 AI 상담 도우미예요. 24시간 언제든 도와드립니다.\n\n글로 쓰기 불편하시면 아래 🎤 버튼을 누르고 말씀하셔도 돼요.';

  const STYLES = `
    /* === MyHear 24 Chatbot Styles (격리 namespace: my24-) === */
    .my24-reset, .my24-reset * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
      font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
    }
    #my24-toggle {
      position: fixed; bottom: 24px; right: 24px;
      width: 64px; height: 64px; border-radius: 50%;
      background: linear-gradient(135deg, #2C5F4F 0%, #4A8B7A 100%);
      color: white; border: none; cursor: pointer;
      box-shadow: 0 6px 20px rgba(44,95,79,0.35);
      z-index: 99998;
      font-size: 11px; font-weight: 800; letter-spacing: -0.02em;
      line-height: 1;
      display: flex; align-items: center; justify-content: center; flex-direction: column; gap: 2px;
      transition: transform 0.2s ease;
      animation: my24-pulse 2.5s infinite;
      font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    #my24-toggle:hover { transform: scale(1.08); }
    #my24-toggle .my24-tag-my { font-size: 10px; opacity: 0.9; }
    #my24-toggle .my24-tag-24 { font-size: 18px; }
    #my24-toggle.my24-open { animation: none; }
    @keyframes my24-pulse {
      0%,100% { box-shadow: 0 6px 20px rgba(44,95,79,0.35), 0 0 0 0 rgba(44,95,79,0.5); }
      50%     { box-shadow: 0 6px 20px rgba(44,95,79,0.35), 0 0 0 16px rgba(44,95,79,0); }
    }
    #my24-modal {
      position: fixed; bottom: 100px; right: 24px;
      width: 400px; height: 640px; max-height: calc(100vh - 130px);
      background: #FAFAF7; border-radius: 20px;
      box-shadow: 0 20px 60px rgba(0,0,0,0.18);
      display: none; flex-direction: column; overflow: hidden;
      z-index: 99999;
      font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, sans-serif;
      color: #1A1A1A;
    }
    #my24-modal.my24-open { display: flex; animation: my24-slidein 0.25s ease; }
    @keyframes my24-slidein {
      from { opacity: 0; transform: translateY(20px); }
      to   { opacity: 1; transform: translateY(0); }
    }
    @media (max-width: 480px) {
      #my24-modal { width: calc(100vw - 16px); right: 8px; bottom: 90px; height: calc(100vh - 110px); }
      #my24-toggle { bottom: 16px; right: 16px; width: 56px; height: 56px; }
    }
    .my24-header {
      background: #FFFFFF; border-bottom: 1px solid #E8E5DC;
      padding: 16px 20px; display: flex; align-items: center; gap: 12px;
    }
    .my24-avatar {
      width: 40px; height: 40px; border-radius: 12px;
      background: linear-gradient(135deg,#2C5F4F 0%,#4A8B7A 100%);
      color: white; font-weight: 800;
      display: flex; flex-direction: column; align-items: center; justify-content: center;
      line-height: 1; flex-shrink: 0;
    }
    .my24-avatar .my24-tag-my { font-size: 9px; opacity: 0.9; }
    .my24-avatar .my24-tag-24 { font-size: 14px; }
    .my24-title-area { flex: 1; min-width: 0; }
    .my24-title { font-size: 15px; font-weight: 700; letter-spacing: -0.02em; }
    .my24-subtitle { font-size: 11px; color: #6B6B6B; margin-top: 2px; letter-spacing: -0.01em; }
    #my24-close {
      background: none; border: none; cursor: pointer;
      width: 32px; height: 32px; border-radius: 8px;
      color: #6B6B6B; font-size: 22px; line-height: 1;
      display: flex; align-items: center; justify-content: center;
      transition: background 0.15s ease;
      font-family: inherit;
    }
    #my24-close:hover { background: #F0EFEA; color: #1A1A1A; }
    #my24-mission {
      background: #1A1A1A; color: #FAFAF7;
      padding: 10px 20px; text-align: center;
      font-size: 12px; letter-spacing: -0.01em;
    }
    #my24-mission strong { color: #FFD580; }
    #my24-messages {
      flex: 1; overflow-y: auto; padding: 20px;
      display: flex; flex-direction: column; gap: 16px;
    }
    .my24-msg { display: flex; align-items: flex-start; gap: 8px; max-width: 100%; }
    .my24-msg.my24-user { justify-content: flex-end; }
    .my24-mini-avatar {
      width: 28px; height: 28px; border-radius: 8px;
      background: linear-gradient(135deg,#2C5F4F 0%,#4A8B7A 100%);
      color: white; font-weight: 800;
      display: flex; flex-direction: column; align-items: center; justify-content: center;
      line-height: 1; flex-shrink: 0; margin-top: 2px;
    }
    .my24-mini-avatar .my24-tag-my { font-size: 7px; opacity: 0.9; }
    .my24-mini-avatar .my24-tag-24 { font-size: 10px; }
    .my24-bubble {
      max-width: 78%; padding: 12px 16px;
      font-size: 15px; line-height: 1.65; letter-spacing: -0.01em;
      white-space: pre-wrap; word-break: keep-all;
    }
    .my24-msg.my24-assistant .my24-bubble {
      background: #FFFFFF; border: 1px solid #E8E5DC;
      border-radius: 18px 18px 18px 4px; color: #1A1A1A;
    }
    .my24-msg.my24-user .my24-bubble {
      background: #1A1A1A; color: #FAFAF7;
      border-radius: 18px 18px 4px 18px;
    }
    .my24-typing {
      display: flex; gap: 4px; padding: 14px 16px;
      background: #FFFFFF; border: 1px solid #E8E5DC;
      border-radius: 18px 18px 18px 4px;
    }
    .my24-typing span {
      width: 6px; height: 6px; border-radius: 50%;
      background: #9CA39A; display: inline-block;
      animation: my24-bounce 1.4s infinite ease-in-out;
    }
    .my24-typing span:nth-child(2) { animation-delay: 0.2s; }
    .my24-typing span:nth-child(3) { animation-delay: 0.4s; }
    @keyframes my24-bounce {
      0%,80%,100% { transform: scale(0.6); opacity: 0.5; }
      40% { transform: scale(1); opacity: 1; }
    }
    .my24-error {
      padding: 10px 14px; border-radius: 10px;
      background: #FEF2F2; color: #991B1B;
      font-size: 12px; letter-spacing: -0.01em;
    }
    .my24-quick-title {
      font-size: 10px; color: #9CA39A; text-transform: uppercase;
      letter-spacing: 0.08em; font-weight: 600; margin-top: 12px;
    }
    .my24-quick { display: flex; flex-direction: column; gap: 6px; margin-top: 8px; }
    .my24-quick button {
      padding: 12px 14px; border-radius: 10px;
      border: 1px solid #E8E5DC; background: #FFFFFF;
      color: #1A1A1A; font-size: 14px; text-align: left;
      cursor: pointer; font-family: inherit;
      transition: all 0.15s ease; letter-spacing: -0.01em;
      line-height: 1.4;
    }
    .my24-quick button:hover { border-color: #2C5F4F; background: #F0F4F1; }
    #my24-input-area {
      border-top: 1px solid #E8E5DC;
      background: #FFFFFF;
      padding: 12px 16px;
    }
    #my24-input-row { display: flex; gap: 6px; align-items: flex-end; }
    #my24-mic, #my24-send {
      border: 1px solid #E8E5DC; border-radius: 14px;
      cursor: pointer; font-family: inherit;
      transition: all 0.15s ease; flex-shrink: 0;
    }
    #my24-mic {
      padding: 12px 14px; background: #FFFFFF; color: #1A1A1A;
      font-size: 18px; min-width: 50px;
    }
    #my24-mic.my24-listening {
      background: #DC2626; color: white; border-color: #DC2626;
      animation: my24-mic-pulse 1.5s infinite;
    }
    @keyframes my24-mic-pulse {
      0%,100% { box-shadow: 0 0 0 0 rgba(220,38,38,0.6); }
      50%     { box-shadow: 0 0 0 10px rgba(220,38,38,0); }
    }
    #my24-input {
      flex: 1; padding: 12px 14px; border-radius: 14px;
      border: 1px solid #E8E5DC; font-size: 15px;
      font-family: inherit; resize: none; outline: none;
      max-height: 100px; line-height: 1.5; letter-spacing: -0.01em;
      background: #FAFAF7; min-width: 0;
    }
    #my24-input.my24-listening { background: #FEF2F2; }
    #my24-input::placeholder { color: #9CA39A; }
    #my24-input:focus { border-color: #2C5F4F; }
    #my24-send {
      padding: 12px 16px; background: #1A1A1A; color: #FAFAF7;
      border: none; font-size: 14px; font-weight: 600;
      letter-spacing: -0.01em;
    }
    #my24-send:disabled { background: #D4D1C7; cursor: not-allowed; }
    #my24-disclaimer {
      margin-top: 8px; font-size: 10px; color: #9CA39A;
      text-align: center; letter-spacing: -0.005em; line-height: 1.4;
    }
  `;

  const HTML = `
    <button id="my24-toggle" aria-label="MyHear 24 AI 상담 열기">
      <span class="my24-tag-my">My</span>
      <span class="my24-tag-24">24</span>
    </button>
    <div id="my24-modal" role="dialog" aria-label="MyHear 24 AI 상담">
      <div class="my24-header">
        <div class="my24-avatar">
          <span class="my24-tag-my">My</span>
          <span class="my24-tag-24">24</span>
        </div>
        <div class="my24-title-area">
          <div class="my24-title">MyHear 24</div>
          <div class="my24-subtitle">AI 상담 · 보청기 에디터 운영 · 24시간</div>
        </div>
        <button id="my24-close" aria-label="닫기">×</button>
      </div>
      <div id="my24-mission">
        난청 방치 평균 <strong>7년</strong> → MyHear에서 <strong>7분</strong>
      </div>
      <div id="my24-messages"></div>
      <div id="my24-input-area">
        <div id="my24-input-row">
          <button id="my24-mic" aria-label="음성 입력">🎤</button>
          <textarea id="my24-input" rows="1" placeholder="메시지 입력 또는 🎤 음성"></textarea>
          <button id="my24-send">전송</button>
        </div>
        <div id="my24-disclaimer">
          MyHear 24는 AI 상담 도우미입니다 · 정보 제공 목적이며 의료 진단을 대체하지 않습니다
        </div>
      </div>
    </div>
  `;

  function init() {
    // Style 주입
    const style = document.createElement('style');
    style.id = 'my24-styles';
    style.textContent = STYLES;
    document.head.appendChild(style);

    // HTML 주입 (body 끝)
    const container = document.createElement('div');
    container.id = 'my24-container';
    container.className = 'my24-reset';
    container.innerHTML = HTML;
    document.body.appendChild(container);

    // 상태
    let messages = [];
    let isLoading = false;
    let isListening = false;
    let isOpen = false;
    let recognition = null;

    // 엘리먼트 참조
    const $toggle = document.getElementById('my24-toggle');
    const $modal = document.getElementById('my24-modal');
    const $close = document.getElementById('my24-close');
    const $messages = document.getElementById('my24-messages');
    const $input = document.getElementById('my24-input');
    const $send = document.getElementById('my24-send');
    const $mic = document.getElementById('my24-mic');

    // 음성 인식 초기화
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SR) {
      recognition = new SR();
      recognition.lang = 'ko-KR';
      recognition.continuous = false;
      recognition.interimResults = true;
      recognition.onresult = function(event) {
        let finalText = '';
        for (let i = event.resultIndex; i < event.results.length; i++) {
          if (event.results[i].isFinal) finalText += event.results[i][0].transcript;
        }
        if (finalText) $input.value = $input.value + ($input.value ? ' ' : '') + finalText;
        updateSendUI();
      };
      recognition.onerror = function(e) {
        isListening = false;
        updateMicUI();
        if (e.error === 'not-allowed') showError('마이크 권한이 필요합니다. 브라우저 주소창의 자물쇠 → 마이크 허용을 눌러주세요.');
        else if (e.error === 'no-speech') showError('음성이 감지되지 않았어요. 다시 시도해주세요.');
      };
      recognition.onend = function() {
        isListening = false;
        updateMicUI();
      };
    }

    // 이벤트
    $toggle.addEventListener('click', toggle);
    $close.addEventListener('click', toggle);
    $mic.addEventListener('click', toggleVoice);
    $send.addEventListener('click', send);
    $input.addEventListener('keydown', function(e) {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
    });
    $input.addEventListener('input', updateSendUI);

    function toggle() {
      isOpen = !isOpen;
      if (isOpen) {
        $modal.classList.add('my24-open');
        $toggle.classList.add('my24-open');
        if (messages.length === 0) {
          addAssistantMessage(INITIAL_GREETING);
          renderQuickPrompts();
        }
      } else {
        $modal.classList.remove('my24-open');
        $toggle.classList.remove('my24-open');
        if (isListening) recognition?.stop();
      }
    }

    function toggleVoice() {
      if (!recognition) {
        showError('이 브라우저는 음성 입력을 지원하지 않습니다. Chrome 또는 Safari를 사용해주세요.');
        return;
      }
      if (isListening) { recognition.stop(); }
      else {
        try {
          recognition.start();
          isListening = true;
          updateMicUI();
        } catch (e) { /* 이미 시작됨 */ }
      }
    }

    function updateMicUI() {
      if (isListening) {
        $mic.classList.add('my24-listening');
        $mic.textContent = '🔴';
        $input.classList.add('my24-listening');
        $input.placeholder = '듣고 있어요... 천천히 말씀해주세요';
      } else {
        $mic.classList.remove('my24-listening');
        $mic.textContent = '🎤';
        $input.classList.remove('my24-listening');
        $input.placeholder = '메시지 입력 또는 🎤 음성';
      }
    }

    async function send() {
      const text = $input.value.trim();
      if (!text || isLoading) return;
      if (isListening) recognition?.stop();

      addUserMessage(text);
      $input.value = '';
      isLoading = true;
      updateSendUI();
      showTyping();

      try {
        const res = await fetch(WORKER_URL, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ messages: messages })
        });
        const data = await res.json();
        hideTyping();
        if (!res.ok || data.error) showError(data.error || '응답을 받지 못했습니다');
        else addAssistantMessage(data.reply || '');
      } catch (err) {
        hideTyping();
        showError('연결에 실패했습니다. 잠시 후 다시 시도해주세요.');
      } finally {
        isLoading = false;
        updateSendUI();
      }
    }

    function updateSendUI() {
      $send.disabled = isLoading || !$input.value.trim();
    }

    function addUserMessage(content) {
      messages.push({ role: 'user', content: content });
      const div = document.createElement('div');
      div.className = 'my24-msg my24-user';
      const bubble = document.createElement('div');
      bubble.className = 'my24-bubble';
      bubble.textContent = content;
      div.appendChild(bubble);
      $messages.appendChild(div);
      scrollToBottom();
      removeQuickPrompts();
    }

    function addAssistantMessage(content) {
      messages.push({ role: 'assistant', content: content });
      const div = document.createElement('div');
      div.className = 'my24-msg my24-assistant';
      div.innerHTML = '<div class="my24-mini-avatar"><span class="my24-tag-my">My</span><span class="my24-tag-24">24</span></div>';
      const bubble = document.createElement('div');
      bubble.className = 'my24-bubble';
      bubble.textContent = content;
      div.appendChild(bubble);
      $messages.appendChild(div);
      scrollToBottom();
    }

    function showTyping() {
      const wrap = document.createElement('div');
      wrap.id = 'my24-typing-wrap';
      wrap.className = 'my24-msg my24-assistant';
      wrap.innerHTML = '<div class="my24-mini-avatar"><span class="my24-tag-my">My</span><span class="my24-tag-24">24</span></div><div class="my24-typing"><span></span><span></span><span></span></div>';
      $messages.appendChild(wrap);
      scrollToBottom();
    }
    function hideTyping() {
      const t = document.getElementById('my24-typing-wrap');
      if (t) t.remove();
    }

    function showError(msg) {
      const div = document.createElement('div');
      div.className = 'my24-error';
      div.textContent = msg;
      $messages.appendChild(div);
      scrollToBottom();
    }

    function renderQuickPrompts() {
      const wrap = document.createElement('div');
      wrap.id = 'my24-quick-wrap';
      const title = document.createElement('div');
      title.className = 'my24-quick-title';
      title.textContent = '자주 묻는 질문 · 클릭만 하셔도 돼요';
      wrap.appendChild(title);
      const quick = document.createElement('div');
      quick.className = 'my24-quick';
      QUICK_PROMPTS.forEach(function(q) {
        const btn = document.createElement('button');
        btn.textContent = q;
        btn.addEventListener('click', function() {
          $input.value = q;
          updateSendUI();
          $input.focus();
        });
        quick.appendChild(btn);
      });
      wrap.appendChild(quick);
      $messages.appendChild(wrap);
      scrollToBottom();
    }

    function removeQuickPrompts() {
      const q = document.getElementById('my24-quick-wrap');
      if (q) q.remove();
    }

    function scrollToBottom() {
      setTimeout(function() { $messages.scrollTop = $messages.scrollHeight; }, 50);
    }
  }

  // DOM 준비되면 초기화
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
