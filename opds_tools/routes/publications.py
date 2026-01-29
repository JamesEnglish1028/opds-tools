# opds_tools/routes/publications.py

from flask import Blueprint, render_template, request, redirect, url_for, flash
from opds_tools.models import db, Publication, Catalog

publications_bp = Blueprint("publications", __name__, template_folder="../templates")

@publications_bp.route("/publications")
def list_publications():
    publications = Publication.query.order_by(Publication.created_at.desc()).all()
    return render_template("publications/list.html", publications=publications)

@publications_bp.route("/publications/<int:id>")
def view_publication(id):
    publication = Publication.query.get_or_404(id)
    return render_template("publications/view_publication.html", publication=publication)

@publications_bp.route("/publications/new", methods=["GET", "POST"])
def create_publication():
    if request.method == "POST":
        title = request.form["title"]
        isbn = request.form.get("isbn")
        author = request.form.get("author")
        language = request.form.get("language")
        publisher = request.form.get("publisher")

        pub = Publication(title=title, isbn=isbn, author=author, language=language, publisher=publisher)
        db.session.add(pub)
        db.session.commit()

        flash("Publication created successfully.", "success")
        return redirect(url_for("publications.list_publications"))

    return render_template("publications/form.html")

@publications_bp.route("/publications/<int:id>/delete", methods=["POST"])
def delete_publication(id):
    publication = Publication.query.get_or_404(id)
    db.session.delete(publication)
    db.session.commit()
    flash("Publication deleted.", "warning")
    return redirect(url_for("publications.list_publications"))
