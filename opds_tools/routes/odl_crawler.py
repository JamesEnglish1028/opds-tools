from flask import Blueprint, render_template, request, redirect, flash, url_for
import requests
from datetime import datetime
from opds_tools.models import db
from opds_tools.models.odl_feed import ODLFeed
from opds_tools.models.ODLpublications import ODLPublication
from opds_tools.util.parser import extract_publications_with_odl
from sqlalchemy import cast, String
from sqlalchemy.dialects.postgresql import JSONB
from collections import Counter

# ✅ Define the blueprint BEFORE you use it
odl_crawler_bp = Blueprint("odl_crawler", __name__)

@odl_crawler_bp.route("/odl-crawler", methods=["GET", "POST"])
def crawl_odl_feed():
    if request.method == "POST":
        feed_id = request.form.get("feed_id")
        feed = ODLFeed.query.get_or_404(feed_id)
        auth = (feed.username, feed.password) if feed.username and feed.password else None

        all_publications = []

        def crawl(url):
            try:
                r = requests.get(url, auth=auth, timeout=10)
                r.raise_for_status()
                data = r.json()
                extracted = extract_publications_with_odl(data)
                all_publications.extend(extracted)

                for link in data.get("links", []):
                    if link.get("rel") == "next":
                        return crawl(link.get("href"))
            except Exception as e:
                flash(f"Error while crawling: {e}", "danger")

        crawl(feed.url)

        for pub in all_publications:
            db.session.add(ODLPublication(data=pub, feed=feed))
        db.session.commit()

        flash(f"Stored {len(all_publications)} ODL publications.", "success")
        return redirect(url_for("odl_crawler.crawl_odl_feed", feed_id=feed.id))

    # GET path
    feed_id = request.args.get("feed_id")
    feed = ODLFeed.query.get(feed_id) if feed_id else None
    pubtype_counts = {}
    format_counts = {}

    if feed:
        records = ODLPublication.query.filter_by(feed_id=feed.id).all()
        for record in records:
            pub_type = record.data.get("metadata", {}).get("@type", "Unknown")
            pubtype_counts[pub_type] = pubtype_counts.get(pub_type, 0) + 1

                    # Extract formats from ODL licenses
            odl = record.data.get("odl")
            if odl and isinstance(odl.get("format"), list):
                for fmt in odl["format"]:
                    format_counts[fmt] = format_counts.get(fmt, 0) + 1

    feeds = ODLFeed.query.all()
    return render_template(
        "crawl_odl.html", 
        feeds=feeds, 
        feed=feed, 
        pubtype_counts=pubtype_counts,
        format_counts=format_counts
        )


@odl_crawler_bp.route("/odl-feeds")
def list_odl_feeds():
    feeds = ODLFeed.query.all()
    feed_stats = {}

    for feed in feeds:
        count = ODLPublication.query.filter_by(feed_id=feed.id).count()
        feed_stats[feed.id] = count

    return render_template("odl_feed_list.html", feeds=feeds, feed_stats=feed_stats)


@odl_crawler_bp.route("/odl-feeds/<int:feed_id>/publications", methods=["GET"])
def view_odl_publications(feed_id):
    feed = ODLFeed.query.get_or_404(feed_id)
    query = ODLPublication.query.filter(
        ODLPublication.feed_id == feed.id,
        ODLPublication.data.isnot(None)
    )

    # Filters
    title_filter = request.args.get("title", "").lower()
    format_filter = request.args.get("format", "")
    pub_type_filter = request.args.get("publication_type", "")
    term_filter = request.args.get("term", "")
    term_value = None

    # Fetch records for filtering and dropdown data
    all_records = ODLPublication.query.filter_by(feed_id=feed.id).filter(ODLPublication.data.isnot(None)).all()

    all_formats = set()
    all_types = set()
    terms_dict = {}

    format_counts = Counter()
    type_counts = Counter()
    term_key_counts = Counter()

    for record in all_records:
        data = record.data
        if not isinstance(data, dict):
            continue

        odl_section = data.get("odl")
        if isinstance(odl_section, dict):
            formats = odl_section.get("format", [])
            if isinstance(formats, list):
                format_counts.update(formats)
                all_formats.update(formats)

            terms = odl_section.get("terms", {})
            if isinstance(terms, dict):
                for k, v in terms.items():
                    term_key_counts[k] += 1
                    terms_dict[k] = v

        pub_type = data.get("metadata", {}).get("@type")
        if pub_type:
            type_counts[pub_type] += 1
            all_types.add(pub_type)

    # Determine term_value after terms_dict is populated
    term_value = terms_dict.get(term_filter)

    # Apply filters to query
    if title_filter:
        query = query.filter(
            cast(ODLPublication.data["title"], String).ilike(f"%{title_filter}%")
        )
    if format_filter:
        query = query.filter(
            cast(ODLPublication.data["odl"]["format"], String).ilike(f"%{format_filter}%")
        )
    if pub_type_filter:
        query = query.filter(
            cast(ODLPublication.data["metadata"]["@type"], String).ilike(f"%{pub_type_filter}%")
        )
    if term_filter and term_value is not None:
        query = query.filter(
            cast(ODLPublication.data["odl"]["terms"][term_filter], String).ilike(f"%{term_value}%")
        )

    publications = query.order_by(ODLPublication.crawled_at.desc()).all()

    return render_template(
        "view_odl_publications.html",
        feed=feed,
        publications=publications,
        all_formats=sorted(all_formats),
        all_types=sorted(all_types),
        available_terms=terms_dict,
        selected_format=format_filter,
        selected_type=pub_type_filter,
        search_title=title_filter,
        selected_term_key=term_filter,
        selected_term_value=term_value,
        format_counts=format_counts,
        type_counts=type_counts,
        term_key_counts=term_key_counts,
    )
