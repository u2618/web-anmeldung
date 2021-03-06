#!/usr/bin/env python
# -*- coding: utf-8 -*-

from bottle import route, run, static_file, post, get, request, template, response, redirect, error, abort
from mailer import confirmation_mail
import filedict
import json
import time
import string
from random import choice
from datadump import pp, registrants_by_university
from data import unis, exkursionen, essen, tshirts, exkursionen_dict, essen_dict, tshirts_dict, unis_dict
import re
from hacks import CustomWSGIRefServer
import argparse

d = filedict.FileDict(filename="data/anmeldungen.dict.sqlite")

CLOSED = False
PASSWORD = ""

a_p_i = filedict.FileDict(filename="data/anmeldungen-pro-ip.dict.sqlite")
MAX_PER_IP = 15

def check_registrant(reg):
    #return validate_email(reg['email'])
    return True

def create_id(size=8):
    return ''.join([choice(string.letters + string.digits) for i in range(size)])

def unixtime():
    return int(time.time())

@get('/')
def home():
    return template('home', closed=CLOSED)

@get('/anmelden')
def signup():
    if CLOSED:
        redirect('/')
        return
    return template('anmelden', unis=unis, exkursionen=exkursionen, essen=essen, tshirts=tshirts, error=None)

class ValidationError(NameError):
    pass

@post('/anmelden')
def signup_submit():
    if CLOSED:
        redirect('/')
        return
    reg = dict() # we store the registrant's details in a dictionary
    error = None
    # parse and validate user input
    reg['notes'] = u""
    reg['tshirts'] = u""
    reg['food'] = u""
    reg['exkursion1'], reg['exkursion2'], reg['exkursion3'] = (u"", u"", u"")
    reg['arbeitskreise'] = u""
    reg['university_alt'] = u""
    reg['university'] = u""
    reg['nick_name'] = u""
    reg['email'] = u""
    reg['last_name'] = u""
    reg['first_name'] = u""
    try:
        reg['notes'] = request.forms.getunicode('notes').strip()
    except:
        error = ValidationError(u'Fehler mit dem Feld Sonstige Wünsche.')
    try:
        reg['tshirt'] = request.forms.getunicode('tshirt').strip()
        tshirts_dict[reg['tshirt']]
    except:
        error = ValidationError("Bitte T-Shirt korrekt angeben.")
    try:
        reg['food'] = request.forms.getunicode('food').strip()
    except:
        error = ValidationError(u'Bitte eine Wahl für das Essen treffen.')
    try:
        reg['exkursion3'] = request.forms.getunicode('exkursion3').strip()
        reg['exkursion2'] = request.forms.getunicode('exkursion2').strip()
        reg['exkursion1'] = request.forms.getunicode('exkursion1').strip()
        exkursionen_dict[reg['exkursion1']] and exkursionen_dict[reg['exkursion2']] and exkursionen_dict[reg['exkursion3']]
    except:
        error = ValidationError(u"Exkursionen nicht ordentlich angegeben.")
    try:
        reg['arbeitskreise'] = request.forms.getunicode('arbeitskreise').strip()
    except:
        raise ValidationError(u'Arbeitskreise nicht ordentlich angegeben.')
    try:
        reg['university_alt'] = request.forms.getunicode('university_alt').strip()
    except:
        raise ValidationError(u'Alternative Universität nicht ordentlich angegeben.')
    try:
        reg['university'] = request.forms.getunicode('university').strip()
    except:
        raise ValidationError(u'Universität nicht ordentlich angegeben.')
    if not (reg['university'] == u'n-i-l' or reg['university'] == u'b-w') and reg['university_alt']:
        error = ValidationError(u'Bitte entweder Universität aus Liste auswählen oder sie selbst in das Textfeld eingeben') 
    try:
        reg['nick_name'] = request.forms.getunicode('nick_name').strip()
    except:
        raise ValidationError(u'Feld Nickname fehlt.')
    try:
        reg['email'] = request.forms.getunicode('email_addr').strip()
        if re.match(u"^[a-zA-Z0-9\.\_%\-\+]+@[a-zA-Z0-9._%-]+\.[a-zA-Z]{2,6}$", reg['email']) == None:
            raise
    except:
        error = ValidationError(u"Bitte gültige E-Mail Adresse angeben.")
    try:
        reg['last_name'] = request.forms.getunicode('last_name').strip().title()
        if reg['last_name'] == u'': raise
    except:
        raise ValidationError(u'Bitte Nachnamen angeben')
    try:
        reg['first_name'] = request.forms.getunicode('first_name').strip().title()
        if reg['first_name'] == u'': raise
    except:
        error = ValidationError(u'Bitte Vornamen angeben')
    try:
        a_p_i[request.remote_route[0]]
    except:
        a_p_i[request.remote_route[0]] = 0
    a_p_i[request.remote_route[0]] += 1
    if a_p_i[request.remote_route[0]] > MAX_PER_IP:
        error = ValidationError(u"Nicht mehr als {0} Anmeldungen pro IP Adresse erlaubt!".format(MAX_PER_IP))
    if error:
        return template('anmelden', unis=unis, exkursionen=exkursionen, essen=essen, tshirts=tshirts, registrant=reg, error=error.message)
    # set up less critical parameters
    reg['id'] = create_id()
    reg['time'] = unixtime()
    reg['ip'] = request.remote_route[0]
    reg['confirmed'] = False
    # store the registrant in the SQlite based dictionary
    try:
        confirmation_mail(reg)
    except:
        return template('anmelden', unis=unis, exkursionen=exkursionen, essen=essen, tshirts=tshirts, registrant=reg, error=u"Konnte Bestätigungs-E-Mail nicht versenden. Stimmt deine E-Mail Adresse?")
    d[reg['id']] = reg
    redirect('/anmeldung/erfolgreich')

@get('/anmeldung/erfolgreich')
def success():
    return template('info', message_title="Anmeldung erfolgreich", alert="Anmeldung erfolgreich abgeschlossen.", message="Jetzt bitte E-Mails checken und die Anmeldung bestätigen!")

@get('/anmeldung/unbekannt')
def unknown_id():
    return template('warning', message_title="Fehler", message="Deine Anmeldung ist uns nicht bekannt. Bitte kontaktiere uns, wenn du dir sicher bist, dass der Bestätigungs-Link funktionieren sollte.")

@get('/confirm/<id:re:[a-zA-Z0-9]+>')
def confirm(id):
    time.sleep(2.)
    try:
        reg = d[id]
    except:
        redirect('/anmeldung/unbekannt')
    if reg['confirmed']:
        return template('info', message_title="Anmeldungs-Bestätigung", alert="Alles in Ordnung", message="Die Anmeldung wurde bereits zuvor bestätigt.")
    else:
        reg['confirmed'] = unixtime()
        d[id] = reg
        return template('info', message_title="Anmeldungs-Bestätigung", alert="Danke.", message="Deine Anmeldung wurde erfolgreich bestätigt.")

@route('/static/<path:path>')
def callback(path):
    return static_file(path, root='./static')

@route('/:filename#favicon\.ico|robots\.txt#')
def send_special(filename):
    if filename == 'favicon.ico': filename = 'images/zapf_favicon.ico'
    return static_file(filename, root='./static')

@get('/anmeldungen')
def anmeldungen():
    return template('participants', rbu=registrants_by_university(d.items()))

@get('/liste/json')
def dump_json():
    if not request.GET.get('password', '').strip() == PASSWORD:
        abort(403, 'not allowed')
    response.headers['Content-Type'] = 'text/plain; charset=UTF8'
    return json.dumps(list(d.items()), sort_keys=True, indent=2)

@get('/liste/csv')
def dump_csv():
    if not request.GET.get('password', '').strip() == PASSWORD:
        abort(403, 'not allowed')
    response.headers['Content-Type'] = 'text/plain; charset=UTF8'
    return pp(d.items())

@error(403)
def error404(error):
    return template('warning', message_title="Fehler 403", message="Nicht erlaubt.")

@error(404)
def error404(error):
    return template('warning', message_title="Fehler 404", message="Die aufgerufene Seite existiert nicht.")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
      description='Start a server to store location information.' )
    parser.add_argument('-s', '--password',
      help='The password needed to access the data.')
    parser.add_argument('-p', '--port', type=int, default=8080,
      help='The port to run the web server on.')
    parser.add_argument('-c', '--closed', action='store_true',
      help='Registration is closed.')
    parser.add_argument('-d', '--debug', action='store_true',
      help='Start in debug mode (with verbose HTTP error pages.')
    args = parser.parse_args()
    if args.closed:
        CLOSED = True
    if args.password:
        PASSWORD = args.password
    else:
        PASSWORD = create_id(50)
    print "Password for the data URLs: " + PASSWORD
    if args.debug:
        run(host='0.0.0.0', server=CustomWSGIRefServer, port=args.port, debug=True, reloader=True)
    else:
        run(host='0.0.0.0', server=CustomWSGIRefServer, port=args.port)

