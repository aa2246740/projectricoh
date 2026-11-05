#!/opt/homebrew/bin/python3
"""Query the private, local photo index."""
import argparse
import json
import sqlite3
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--unit', choices=['28mm', '50mm', 'MOUNT', 'unknown'])
    parser.add_argument('--setting')
    parser.add_argument('--iso', type=int)
    parser.add_argument('--pairs', action='store_true')
    parser.add_argument('--used-by')
    parser.add_argument('--content')
    parser.add_argument('--page')
    parser.add_argument('--environment')
    parser.add_argument('--subject')
    parser.add_argument('--limit', type=int, default=0)
    args = parser.parse_args()
    path = Path(__file__).resolve().parent / 'local/index.sqlite'
    if not path.exists():
        parser.error('local index.sqlite is missing')
    db = sqlite3.connect(f'file:{path}?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    clauses, values = [], []
    for column, value in [('unit', args.unit), ('setting', args.setting),
                          ('iso', args.iso), ('page', args.page)]:
        if value is not None:
            clauses.append(f'p.{column} = ? COLLATE NOCASE')
            values.append(value)
    if args.content:
        clauses.append("(p.content = ? COLLATE NOCASE OR CASE p.content WHEN 'screen' THEN 'screen_chart' WHEN 'physical' THEN 'printed_chart' WHEN 'probe' THEN 'probe_page' ELSE p.content END = ? COLLATE NOCASE OR EXISTS (SELECT 1 FROM labels l WHERE l.sha256=p.sha256 AND l.content=? COLLATE NOCASE))")
        values.extend([args.content, args.content, args.content])
    if args.environment:
        clauses.append("EXISTS (SELECT 1 FROM labels l WHERE l.sha256=p.sha256 AND l.environment=? COLLATE NOCASE)")
        values.append(args.environment)
    if args.subject:
        clauses.append("EXISTS (SELECT 1 FROM labels l, json_each(l.subjects) j WHERE l.sha256=p.sha256 AND j.value=? COLLATE NOCASE)")
        values.append(args.subject)
    if args.pairs:
        clauses.append('(EXISTS(SELECT 1 FROM pairs WHERE dng_sha256=p.sha256 OR jpg_sha256=p.sha256))')
    if args.used_by:
        clauses.append('EXISTS(SELECT 1 FROM uses WHERE sha256=p.sha256 AND research=? COLLATE NOCASE)')
        values.append(args.used_by)
    sql = 'SELECT p.* FROM photos p' + (' WHERE ' + ' AND '.join(clauses) if clauses else '') + ' ORDER BY p.exif_time, p.sha256'
    if args.limit:
        sql += ' LIMIT ?'
        values.append(args.limit)
    for row in db.execute(sql, values):
        result = dict(row)
        digest = result['sha256']
        result['paths'] = [dict(x) for x in db.execute('SELECT path, source, mtime FROM paths WHERE sha256=? ORDER BY path', (digest,))]
        result['pairs'] = [dict(x) for x in db.execute('SELECT * FROM pairs WHERE dng_sha256=? OR jpg_sha256=?', (digest, digest))]
        result['uses'] = [dict(x) for x in db.execute('SELECT research, evidence FROM uses WHERE sha256=? ORDER BY research', (digest,))]
        label = db.execute('SELECT * FROM labels WHERE sha256=?', (digest,)).fetchone()
        result['labels'] = dict(label) if label else None
        if label:
            result['labels']['subjects'] = json.loads(result['labels']['subjects'])
        print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
