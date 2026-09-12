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
