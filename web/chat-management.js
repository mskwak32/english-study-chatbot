/**
 * 사용자의 삭제 확인 뒤에만 서버 삭제 요청을 수행합니다.
 *
 * @param {{id: number, title: string}} chat 삭제 후보 채팅입니다.
 * @param {object} dependencies 외부 동작을 주입합니다.
 * @param {(chat: {id: number, title: string}) => boolean} dependencies.confirmDelete 확인 대화상자 함수입니다.
 * @param {(chatId: number) => Promise<void>} dependencies.deleteChat 서버 삭제 함수입니다.
 * @returns {Promise<boolean>} 삭제하면 true, 취소하면 false입니다.
 */
export async function deleteConfirmedChat(
  chat,
  { confirmDelete, deleteChat },
) {
  if (!confirmDelete(chat)) {
    return false;
  }

  await deleteChat(chat.id);
  return true;
}
