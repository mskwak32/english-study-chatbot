/**
 * 메시지 목록을 가장 최근 메시지가 보이는 위치로 이동합니다.
 *
 * @param {{scrollHeight: number, scrollTop: number}} messageList 스크롤할 메시지 목록입니다.
 */
export function scrollMessageListToBottom(messageList) {
  messageList.scrollTop = messageList.scrollHeight;
}
