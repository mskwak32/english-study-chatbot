"""Raspberry Pi에서 Ollama 모델의 응답 시간과 메모리 사용량을 측정합니다."""

import argparse
import json
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

# scripts/에서 실행해도 backend/app 패키지를 가져올 수 있게 합니다.
BACKEND_DIRECTORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIRECTORY))

from app.agent.protocol import AGENT_RESPONSE_SCHEMA

PROMPT_MESSAGES = [
    {
        "role": "system",
        "content": (
            "You are an English tutor. "
            "Always return action 'reply'. "
            "Return only JSON that follows the supplied schema."
        ),
    },
    {
        "role": "user",
        "content": (
            "In 70 to 90 English words, explain why learners should "
            "practice speaking English regularly."
        ),
    },
]

OLLAMA_PROCESS_NAMES = {
    "ollama",
    "llama-server",
}


@dataclass(frozen=True)
class BenchmarkResult:
    """한 번의 모델 요청에서 측정한 결과를 표현합니다."""

    label: str
    first_content_seconds: float
    total_seconds: float
    received_characters: int
    start_rss_mib: float
    peak_rss_mib: float
    swap_before_mib: float | None
    swap_after_mib: float | None
    load_seconds: float | None
    prompt_evaluation_seconds: float | None
    evaluation_seconds: float | None


class OllamaMemoryMonitor:
    """Ollama 프로세스의 RSS 메모리 사용량을 주기적으로 기록합니다."""

    def __init__(self, interval_seconds: float) -> None:
        """RSS 샘플 간격을 설정하고 측정 상태를 초기화합니다."""
        self._interval_seconds = interval_seconds
        self._samples_mib: list[float] = []
        self._stop_event = threading.Event()
        self._thread = threading.Thread(
            target=self._record_samples,
            daemon=True,
        )

    @staticmethod
    def _read_rss_mib() -> float:
        """Ollama 서버와 모델 runner의 RSS 합계를 MiB로 반환합니다."""
        result = subprocess.run(
            ["ps", "-eo", "rss=,comm=,args="],
            capture_output=True,
            check=False,
            text=True,
        )

        rss_kib = 0

        for line in result.stdout.splitlines():
            fields = line.split(maxsplit=2)

            if len(fields) < 2:
                continue

            rss_text, command_name = fields[:2]

            if command_name in OLLAMA_PROCESS_NAMES:
                rss_kib += int(rss_text)

        return rss_kib / 1024

    def _record_samples(self) -> None:
        """측정이 끝날 때까지 RSS 값을 일정 간격으로 기록합니다."""
        while not self._stop_event.is_set():
            self._samples_mib.append(self._read_rss_mib())
            self._stop_event.wait(self._interval_seconds)

    def start(self) -> None:
        """시작 시점의 RSS를 기록하고 백그라운드 측정을 시작합니다."""
        self._samples_mib.append(self._read_rss_mib())
        self._thread.start()

    def stop(self) -> None:
        """백그라운드 측정을 끝내고 마지막 RSS를 기록합니다."""
        self._stop_event.set()
        self._thread.join()
        self._samples_mib.append(self._read_rss_mib())

    @property
    def start_rss_mib(self) -> float:
        """측정 시작 시점의 RSS를 반환합니다."""
        return self._samples_mib[0]

    @property
    def peak_rss_mib(self) -> float:
        """측정 중 가장 큰 RSS를 반환합니다."""
        return max(self._samples_mib)


def swap_in_use_mib() -> float | None:
    """Linux /proc/meminfo에서 현재 사용 중인 swap을 MiB로 계산합니다."""
    memory_values: dict[str, int] = {}

    try:
        lines = Path("/proc/meminfo").read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return None

    for line in lines:
        key, value, *_ = line.split()
        memory_values[key.rstrip(":")] = int(value)

    swap_total_kib = memory_values.get("SwapTotal")
    swap_free_kib = memory_values.get("SwapFree")

    if swap_total_kib is None or swap_free_kib is None:
        return None

    return (swap_total_kib - swap_free_kib) / 1024


def _duration_seconds(
    response_data: dict[str, object],
    field_name: str,
) -> float | None:
    """Ollama의 나노초 단위 시간 값을 초 단위로 변환합니다."""
    value = response_data.get(field_name)

    if not isinstance(value, int):
        return None

    return value / 1_000_000_000


def benchmark_once(
    client: httpx.Client,
    *,
    model: str,
    label: str,
    interval_seconds: float,
) -> BenchmarkResult:
    """첫 콘텐츠·전체 응답 시간과 수신 길이, RSS·스왑 사용량을 측정합니다.

    스트리밍 요청에 ``format``은 전달하지만 최종 내용의 JSON Schema는 검증하지 않습니다.
    """
    request_body = {
        "model": model,
        "stream": True,
        "format": AGENT_RESPONSE_SCHEMA,
        "messages": PROMPT_MESSAGES,
    }

    memory_monitor = OllamaMemoryMonitor(interval_seconds)
    swap_before_mib = swap_in_use_mib()
    first_content_seconds: float | None = None
    received_content: list[str] = []
    final_response_data: dict[str, object] = {}

    memory_monitor.start()
    started_at = time.perf_counter()

    try:
        with client.stream(
            "POST",
            "/api/chat",
            json=request_body,
        ) as response:
            response.raise_for_status()

            for line in response.iter_lines():
                if not line:
                    continue

                response_data = json.loads(line)

                if not isinstance(response_data, dict):
                    continue

                message_data = response_data.get("message")

                if isinstance(message_data, dict):
                    content = message_data.get("content")

                    if isinstance(content, str) and content:
                        received_content.append(content)

                        if first_content_seconds is None:
                            first_content_seconds = time.perf_counter() - started_at

                if response_data.get("done") is True:
                    final_response_data = response_data
    finally:
        total_seconds = time.perf_counter() - started_at
        memory_monitor.stop()

    if first_content_seconds is None:
        raise RuntimeError("Ollama가 비어 있지 않은 응답 내용을 반환하지 않았습니다.")

    return BenchmarkResult(
        label=label,
        first_content_seconds=first_content_seconds,
        total_seconds=total_seconds,
        received_characters=len("".join(received_content)),
        start_rss_mib=memory_monitor.start_rss_mib,
        peak_rss_mib=memory_monitor.peak_rss_mib,
        swap_before_mib=swap_before_mib,
        swap_after_mib=swap_in_use_mib(),
        load_seconds=_duration_seconds(
            final_response_data,
            "load_duration",
        ),
        prompt_evaluation_seconds=_duration_seconds(
            final_response_data,
            "prompt_eval_duration",
        ),
        evaluation_seconds=_duration_seconds(
            final_response_data,
            "eval_duration",
        ),
    )


def _format_mib(value: float | None) -> str:
    """MiB 값을 사람이 읽기 쉬운 문자열로 변환합니다."""
    if value is None:
        return "확인 불가"

    if value >= 1024:
        return f"{value / 1024:.2f} GiB"

    return f"{value:.1f} MiB"


def _format_seconds(value: float | None) -> str:
    """초 단위 시간을 사람이 읽기 쉬운 문자열로 변환합니다."""
    if value is None:
        return "확인 불가"

    return f"{value:.2f}초"


def print_result(result: BenchmarkResult) -> None:
    """측정 결과 한 건을 출력합니다."""
    print(f"\n[{result.label}]")
    print(f"첫 응답 내용: {_format_seconds(result.first_content_seconds)}")
    print(f"전체 응답 완료: {_format_seconds(result.total_seconds)}")
    print(f"수신 내용 길이: {result.received_characters}자")
    print(f"Ollama 시작 RSS: {_format_mib(result.start_rss_mib)}")
    print(f"Ollama 최대 RSS: {_format_mib(result.peak_rss_mib)}")
    print(f"시작 swap 사용량: {_format_mib(result.swap_before_mib)}")
    print(f"종료 swap 사용량: {_format_mib(result.swap_after_mib)}")
    print(f"모델 로드 시간: {_format_seconds(result.load_seconds)}")
    print(f"프롬프트 처리 시간: {_format_seconds(result.prompt_evaluation_seconds)}")
    print(f"응답 생성 시간: {_format_seconds(result.evaluation_seconds)}")


def positive_number(value: str) -> int:
    """명령행의 양의 정수를 검사합니다."""
    number = int(value)

    if number <= 0:
        raise argparse.ArgumentTypeError("1 이상의 정수를 입력해야 합니다.")

    return number


def ollama_is_available(base_url: str) -> bool:
    """Ollama 서버가 현재 HTTP 요청을 받을 수 있는지 확인합니다."""
    try:
        response = httpx.get(
            f"{base_url.rstrip('/')}/api/version",
            timeout=1.0,
        )
    except httpx.HTTPError:
        return False

    return response.is_success


def start_ollama_server(base_url: str) -> subprocess.Popen[bytes]:
    """Ollama 서버를 시작하고 요청을 받을 때까지 기다립니다."""
    try:
        process = subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError as error:
        raise RuntimeError(
            "ollama 명령을 찾을 수 없습니다. Ollama 설치를 확인해 주세요."
        ) from error

    deadline = time.monotonic() + 15

    while time.monotonic() < deadline:
        if ollama_is_available(base_url):
            return process

        if process.poll() is not None:
            raise RuntimeError("Ollama 서버가 시작 직후 종료되었습니다.")

        time.sleep(0.2)

    process.terminate()
    process.wait(timeout=5)

    raise RuntimeError("15초 안에 Ollama 서버가 준비되지 않았습니다.")


def stop_ollama_server(process: subprocess.Popen[bytes]) -> None:
    """이 스크립트가 시작한 Ollama 서버만 종료합니다."""
    process.terminate()

    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def main() -> int:
    """명령행 인자를 읽고 지정한 횟수만큼 모델을 측정합니다."""
    parser = argparse.ArgumentParser(
        description="Ollama 모델의 응답 시간과 메모리 사용량을 측정합니다."
    )
    parser.add_argument(
        "--model",
        default="gemma3:4b",
        help="측정할 Ollama 모델명입니다.",
    )
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:11434",
        help="Ollama 서버 주소입니다.",
    )
    parser.add_argument(
        "--label",
        default="warm",
        help="출력에 표시할 측정 종류입니다. 예: cold, warm",
    )
    parser.add_argument(
        "--runs",
        type=positive_number,
        default=1,
        help="반복 측정 횟수입니다.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=120.0,
        help="요청 하나가 실패하기까지 기다릴 최대 시간(초)입니다.",
    )
    parser.add_argument(
        "--memory-interval",
        type=float,
        default=0.1,
        help="RSS 메모리 측정 간격(초)입니다.",
    )
    parser.add_argument(
        "--start-ollama",
        action="store_true",
        help="Ollama가 실행 중이지 않으면 ollama serve를 시작합니다.",
    )
    parser.add_argument(
        "--keep-ollama-running",
        action="store_true",
        help="스크립트가 시작한 Ollama 서버를 측정 후에도 종료하지 않습니다.",
    )
    args = parser.parse_args()

    started_ollama_process: subprocess.Popen[bytes] | None = None

    if not ollama_is_available(args.base_url):
        if not args.start_ollama:
            print(
                "Ollama 서버가 실행 중이지 않습니다. "
                "--start-ollama 옵션을 사용하거나 "
                "다른 터미널에서 ollama serve를 실행하세요.",
                file=sys.stderr,
            )
            return 1

        try:
            started_ollama_process = start_ollama_server(
                args.base_url,
            )
        except RuntimeError as error:
            print(f"Ollama 시작에 실패했습니다: {error}", file=sys.stderr)
            return 1

    try:
        with httpx.Client(
            base_url=args.base_url.rstrip("/"),
            timeout=args.timeout,
        ) as client:
            for run_number in range(1, args.runs + 1):
                label = f"{args.label}-{run_number}"

                result = benchmark_once(
                    client,
                    model=args.model,
                    label=label,
                    interval_seconds=args.memory_interval,
                )
                print_result(result)
    except (
        httpx.HTTPError,
        RuntimeError,
        json.JSONDecodeError,
    ) as error:
        print(f"측정에 실패했습니다: {error}", file=sys.stderr)
        return 1
    finally:
        if started_ollama_process is not None and not args.keep_ollama_running:
            stop_ollama_server(started_ollama_process)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
