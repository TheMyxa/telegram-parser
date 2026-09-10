import asyncio

from exporters.telegram_exporter import main, parse_args


if __name__ == "__main__":
    asyncio.run(main(parse_args()))
