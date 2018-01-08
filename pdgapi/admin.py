@api.route("/about", methods=['GET', 'POST'])
@login_required
def http_about():
    data = graphdb.get_db_metadata()
    data.update(infos)
    return jsonify( data )
