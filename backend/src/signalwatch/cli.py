import argparse
import asyncio
import json
from datetime import UTC, datetime

from .collection import CollectionService
from .collectors import ArxivCollector, GitHubCollector, HuggingFaceCollector, RssCollector
from .config import get_settings
from .llm import OllamaProvider
from .logging import configure_logging
from .repository import SupabaseRepository
from .synthesis import generate_report
from .worker import LocalWorker


async def _run(args: argparse.Namespace) -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    repository = SupabaseRepository(settings)
    provider: OllamaProvider | None = None
    try:
        if args.command == "collect":
            github_token = settings.github_token.get_secret_value() if settings.github_token else None
            hf_token = settings.huggingface_token.get_secret_value() if settings.huggingface_token else None
            service = CollectionService(
                repository,
                {
                    "rss": RssCollector(),
                    "github": GitHubCollector(github_token),
                    "arxiv": ArxivCollector(),
                    "huggingface": HuggingFaceCollector(hf_token),
                },
            )
            result = await service.run(args.connector)
        else:
            provider = OllamaProvider(str(settings.ollama_base_url), settings.ollama_model)
            if args.command == "worker":
                worker = LocalWorker(repository, provider, settings.local_worker_id)
                if args.watch:
                    last_daily = last_weekly = None
                    while True:
                        result = await worker.run_once(args.batch_size)
                        now = datetime.now(UTC)
                        if now.hour >= 6 and last_daily != now.date():
                            await generate_report(repository, provider, "Daily")
                            last_daily = now.date()
                        if now.weekday() == 0 and now.hour >= 7 and last_weekly != now.date():
                            await generate_report(repository, provider, "Weekly")
                            last_weekly = now.date()
                        print(json.dumps(result, separators=(",", ":")), flush=True)
                        await asyncio.sleep(args.interval)
                else:
                    result = await worker.run_once(args.batch_size)
            else:
                result = await generate_report(repository, provider, args.report_type)
        print(json.dumps(result, separators=(",", ":")))
    finally:
        if provider:
            await provider.close()
        await repository.close()


def main() -> None:
    parser = argparse.ArgumentParser(prog="signalwatch")
    subparsers = parser.add_subparsers(dest="command", required=True)
    collect = subparsers.add_parser("collect")
    collect.add_argument("--connector", choices=("rss", "github", "arxiv", "huggingface"))
    worker = subparsers.add_parser("worker")
    worker.add_argument("--batch-size", type=int, default=5)
    worker.add_argument("--watch", action="store_true")
    worker.add_argument("--interval", type=int, default=60)
    report = subparsers.add_parser("report")
    report.add_argument("--report-type", choices=("Daily", "Weekly"), required=True)
    asyncio.run(_run(parser.parse_args()))


if __name__ == "__main__":
    main()
