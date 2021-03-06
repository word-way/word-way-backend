import argparse
import csv
import logging
import os
import sys
from pathlib import Path

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.session import Session

from word_way.app import create_app
from word_way.scrapping.word import save_word
from word_way.context import create_session
from word_way.models import SynonymsWordRelation

parser = argparse.ArgumentParser(
    formatter_class=argparse.ArgumentDefaultsHelpFormatter
)
parser.add_argument('-c', '--config', type=str,
                    default=str(os.environ.get('WORD_WAY_ENV', 'prod')))
parser.add_argument(
    '-l', '--line', type=int, default=0,
    help='Options to determine which line synonyms.tsv should be read from'
)

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    args = parser.parse_args()
    wsgi_app = create_app(args.config)
    with wsgi_app.app_context():
        config = wsgi_app.config['APP_CONFIG']
        session = create_session(config)
        scrap_synonyms(session, args.line)


def scrap_synonyms(session: Session, start_line: int):
    """synonyms.tsv 파일을 읽어 유의어 및 단어 정보를 저장하는 함수

    :param session: 사용할 세션
    :type session: :class:`sqlalchemy.orm.session.Session`
    :param start_line: 파일 읽기 시작할 라인
    :type start_line: :class:`int`

    """
    log = logger.getChild('scrap_synonyms')
    synset_list_dir = Path('synonyms.tsv').resolve()

    with open(synset_list_dir, newline='') as f:
        rows = csv.reader(f, delimiter='\t')
        for row_num, row in enumerate(rows):
            if row_num < start_line:
                continue
            lemmas_list = [l.strip() for l in row[3].split(',')]
            log.info(f'Start saving the row {row_num} ({lemmas_list})')
            pronunciation_ids = []
            for lemmas in lemmas_list:
                log.info(f'Start saving the words ({lemmas})')
                pronunciation_id = save_word(lemmas, session)
                if pronunciation_id:
                    pronunciation_ids.append(pronunciation_id)
                log.info(f'Done saving the words ({lemmas})')
            pronunciation_ids = list(set(pronunciation_ids))
            if len(pronunciation_ids) < 2:
                continue
            for i in range(len(pronunciation_ids)):
                synonyms_ids = pronunciation_ids[:]
                criteria_id = synonyms_ids.pop(i)
                log.info(f'Start saving the synonyms ({criteria_id})')
                for synonyms_id in synonyms_ids:
                    relation = SynonymsWordRelation(
                        criteria_id=criteria_id, relation_id=synonyms_id,
                    )
                    session.add(relation)
                    try:
                        session.flush()
                        log.info(f'Done saving the relationship'
                                 f' ({relation.__dict__})')
                    except IntegrityError:
                        session.rollback()
                        log.warning(f'The relationship ({relation.__dict__})'
                                    ' already exists')
                log.info(f'Done saving the synonyms ({criteria_id})')
            session.commit()
            log.info(f'Done saving the row {row_num} ({lemmas_list})')


if __name__ == '__main__':
    main()
