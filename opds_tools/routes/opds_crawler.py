# routes/opds_crawler.py

from flask import Blueprint, render_template, request, redirect, url_for, flash
from opds_tools.models import db, Catalog, Publication
from opds_tools.util.parser import extract_opds_data
import requests
from urllib.parse import urljoin
import logging
from sqlalchemy import func, cast, Text

logger = logging.getLogger(__name__)

crawler_bp = Blueprint('crawler', __name__)

@crawler_bp.route('/catalog-crawler', methods=['GET', 'POST'])
def catalog_crawler():
    catalogs = Catalog.query.all()
    publication_count = 0
    filtered_count = 0
    new_publications = []
    selected_catalog = None

    title = ""
    author = ""
    publisher = ""
    pub_type = ""
    type_counts = []
    pub_id = ""

    if request.method == 'POST':
        if 'crawl' in request.form:
            catalog_id = request.form.get('catalog_id')
            catalog = Catalog.query.get_or_404(catalog_id)

            try:
                count = crawl_opds_feed(catalog.url, catalog_id=catalog.id)
                flash(f"Successfully stored {count} publications from {catalog.title}", "success")

                new_publications = (
                    Publication.query
                    .filter_by(catalog_id=catalog.id)
                    .order_by(Publication.created_at.desc())
                    .limit(count)
                    .all()
                )
                selected_catalog = catalog
                publication_count = Publication.query.filter_by(catalog_id=catalog.id).count()
            except Exception as e:
                logger.exception(f"Failed to crawl catalog {catalog.title}: {e}")
                flash(f"Failed to crawl catalog: {e}", "danger")

        elif 'view' in request.form:
            catalog_id = request.form.get('view_catalog_id')
            selected_catalog = Catalog.query.get_or_404(catalog_id)

            query = Publication.query.filter_by(catalog_id=selected_catalog.id)

            title = request.form.get('search_title', '').strip()
            author = request.form.get('search_author', '').strip()
            publisher = request.form.get('search_publisher', '').strip()
            pub_type = request.form.get('pub_type', '').strip()
            pub_id =request.form.get('idenitifier', '').strip()

            if title:
                query = query.filter(Publication.title.ilike(f"%{title}%"))
            if author:
                query = query.filter(Publication.author.ilike(f"%{author}%"))
            if publisher:
                query = query.filter(Publication.publisher.ilike(f"%{publisher}%"))
            if pub_type:
                query = query.filter(
                    Publication.opds_json['publication_type'].astext == pub_type
                )

            filtered_count = query.count()
            new_publications = query.order_by(Publication.created_at.desc()).limit(100).all()
            publication_count = Publication.query.filter_by(catalog_id=selected_catalog.id).count()

            # Group-by count for publication type
            type_counts = (
                db.session.query(
                    Publication.opds_json['publication_type'].astext.label('type'),
                    func.count().label('count')
                )
                .filter(Publication.catalog_id == selected_catalog.id)
                .group_by(Publication.opds_json['publication_type'].astext)
                .order_by(func.count().desc())
                .all()
            )

    return render_template(
        'catalog_crawler.html',
        catalogs=catalogs,
        new_publications=new_publications,
        selected_catalog=selected_catalog,
        publication_count=publication_count,
        search_title=title,
        search_author=author,
        search_publisher=publisher,
        pub_type=pub_type,
        filtered_count=filtered_count,
        type_counts=type_counts
    )


def crawl_opds_feed(start_url, catalog_id=None, session=None, collected=0, seen_urls=None):
    session = session or requests.Session()
    seen_urls = seen_urls or set()

    if start_url in seen_urls:
        logger.warning(f"Already visited: {start_url}, skipping to avoid loop.")
        return collected
    seen_urls.add(start_url)

    try:
        r = session.get(start_url, timeout=10)
        r.raise_for_status()
        feed = r.json()
    except Exception as e:
        logger.error(f"Failed to fetch {start_url}: {e}")
        return collected

    publications = extract_opds_data(feed, base_url=start_url)
    logger.info(f"Extracted {len(publications)} publications from {start_url}")
    new_count = 0

    for pub_data in publications:
        identifier = pub_data.get("identifier")
        modified = pub_data.get("published") or pub_data.get("modified")
        language = pub_data.get("language")
        if isinstance(language, list):
            language = ", ".join(language)

        if not identifier:
            logger.warning("Skipping publication with no identifier")
            continue

        existing = Publication.query.filter_by(
            catalog_id=catalog_id,
            identifier=identifier,
        ).first()

        if existing and modified and existing.opds_json.get("modified") == modified:
            logger.info(f"Skipping unchanged publication: {identifier}")
            continue

        pub = Publication(
            title=pub_data.get("title", "Untitled"),
            author=pub_data.get("author"),
            language=language,
            publisher=pub_data.get("publisher"),
            identifier=identifier,
            isbn=pub_data.get("isbn13") or pub_data.get("isbn10"),
            opds_json=pub_data,
            catalog_id=catalog_id,
        )
        db.session.add(pub)
        new_count += 1

    try:
        db.session.commit()
        logger.info(f"Committed {new_count} new records to DB")
    except Exception as e:
        logger.exception("Failed to commit publications")
        db.session.rollback()

    collected += new_count

    # Follow rel="next"
    links = feed.get("links", [])
    next_link = next((link for link in links if link.get("rel") == "next"), None)

    if next_link and next_link.get("href"):
        next_url = urljoin(start_url, next_link["href"])
        return crawl_opds_feed(
            next_url,
            catalog_id=catalog_id,
            session=session,
            collected=collected,
            seen_urls=seen_urls
        )

    return collected



@crawler_bp.route('/publications')
def list_publications():
    query = Publication.query

    title = request.args.get('title')
    author = request.args.get('author')
    language = request.args.get('language')
    publisher = request.args.get('publisher')

    if title:
        query = query.filter(Publication.title.ilike(f'%{title}%'))
    if author:
        query = query.filter(Publication.author.ilike(f'%{author}%'))
    if language:
        query = query.filter(Publication.language.ilike(f'%{language}%'))
    if publisher:
        query = query.filter(Publication.publisher.ilike(f'%{publisher}%'))

    publications = query.order_by(Publication.created_at.desc()).all()
    return render_template('publications.html', publications=publications)
