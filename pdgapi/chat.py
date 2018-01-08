#-*- coding:utf-8 -*-

from flask_login import login_required 
from flask import request, jsonify

from reliure.web import ReliureAPI


infos = {
            "desc" : "chat api",
            "version" : "0.1dev"
        }


def chat_api(name, db):
    """ user authentification api """
    from app import login_manager

    api = ReliureAPI(name)
    

    @api.route("/about", methods=['GET', 'POST'])
    def about():
        return jsonify( infos )

    @api.route("/talk", methods=['GET', 'POST'])
    @login_required
    def talk( graph, message, tags):
        """
            send text to graph chan
        """
        return jsonify({ 'message': "bla" })

    
    @api.route("/read", methods=['GET', 'POST'])
    @login_required
    def read( graph, tags, **kwargs ):
        """
            read text from graph chan
            
            graph: namespace
            kwargs :
                count: int max 50
                before: msgid
                after: msgid
        """
        return jsonify({ 'message': "read" })

    return api