/**
 * 메시지 입력에서 전송 단축키를 눌렀는지 판단합니다.
 *
 * 데스크톱에서는 Command/Ctrl+Enter로, 터치 중심 기기에서는 수정자 없는 Enter로
 * 전송합니다. Shift+Enter는 모든 기기에서 줄바꿈으로 남깁니다.
 *
 * @param {{key: string, isComposing?: boolean, metaKey?: boolean, ctrlKey?: boolean, shiftKey?: boolean, altKey?: boolean}} event 키보드 이벤트에 필요한 속성입니다.
 * @param {boolean} hasCoarsePointer 터치 중심 입력 환경인지 여부입니다.
 * @returns {boolean} 폼 전송을 요청해야 하면 true입니다.
 */
export function shouldSubmitMessageShortcut(event, hasCoarsePointer) {
  if (event.isComposing || event.key !== "Enter") {
    return false;
  }

  if (event.shiftKey) {
    return false;
  }

  if (event.metaKey || event.ctrlKey) {
    return true;
  }

  return hasCoarsePointer && !event.altKey;
}

/**
 * DOM에 의존하지 않고 한 건의 메시지 전송 흐름을 구성합니다.
 *
 * @param {object} callbacks 전송과 화면 상태 변경에 사용할 콜백입니다.
 * @param {(content: string) => Promise<object>} callbacks.sendMessage 서버 전송 함수입니다.
 * @param {(message: object) => void} callbacks.onUserMessage 사용자 메시지 처리 함수입니다.
 * @param {(message: object) => void} callbacks.onAssistantMessage 튜터 메시지 처리 함수입니다.
 * @param {(error: unknown) => void} callbacks.onError 전송 오류 처리 함수입니다.
 * @param {(isPending: boolean) => void} callbacks.onPendingChange 전송 대기 상태 처리 함수입니다.
 * @returns {{send: (content: string) => Promise<boolean>}} 전송 함수입니다.
 */
export function createMessageFlow({
  sendMessage,
  onUserMessage,
  onAssistantMessage,
  onError,
  onPendingChange,
}) {
  let isPending = false;

  /**
   * 사용자 메시지를 전송하고 성공 여부를 반환합니다.
   *
   * @param {string} content 보낼 메시지 내용입니다.
   * @returns {Promise<boolean>} 응답을 받으면 true, 실패하거나 중복 요청이면 false입니다.
   */
  async function send(content) {
    if (isPending) {
      return false;
    }

    isPending = true;
    onPendingChange(true);
    onUserMessage({ role: "user", content });

    try {
      const assistantMessage = await sendMessage(content);

      onAssistantMessage(assistantMessage);
      return true;
    } catch (error) {
      onError(error);
      return false;
    } finally {
      isPending = false;
      onPendingChange(false);
    }
  }

  return { send };
}
