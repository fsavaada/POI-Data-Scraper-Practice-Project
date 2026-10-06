"""Run the complete collection/enrichment/export workflow."""
import argparse
from Dianping_Spider import collect_national, enrich_districts, retry_missing, finalize


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workers', type=int, default=3, choices=range(1, 7))
    args = parser.parse_args(argv)
    collect_national.main(['--phase', 'all', '--workers', str(args.workers)])
    retry_missing.main()
    enrich_districts.main()
    finalize.main()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
