#!/usr/bin/python3
"""Check assertion execution and the retained ASCII ceiling."""
import argparse

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--case',choices=('ascii','assertion'),default='ascii')
    args=parser.parse_args()
    if args.case=='assertion':
        assert False
    else:
        assert not all(32<=ord(char)<=126 for char in chr(127))
    print('PASS binding control',args.case)

if __name__=='__main__':
    main()
