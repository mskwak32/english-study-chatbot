/** Manages one chat message request without depending on the DOM. */

export function createMessageFlow({
  sendMessage,
  onUserMessage,
  onAssistantMessage,
  onError,
  onPendingChange,
}) {
  let isPending = false;

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
