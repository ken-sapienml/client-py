# -*- coding: utf-8 -*-

import logging
from fhirclient import client
from fhirclient.models.medication import Medication
from fhirclient.models.medicationrequest import MedicationRequest

from flask import Flask, request, redirect, session, render_template
# from flask import Flask, render_template, redirect, url_for
from flask_bootstrap import Bootstrap
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired

# app setup
smart_defaults = {
    'app_id': 'my_web_app',
    # 'api_base': 'https://fhir-open-api-dstu2.smarthealthit.org',
    # 'api_base': 'https://sb-fhir-stu3.smarthealthit.org/smartstu3/data',
    # 'api_base': 'http://test.fhir.org/r4/',
    # 'api_base': 'https://fhir-open.cerner.com/dstu2/ec2458f2-1e24-41c8-b71b-0e701af7583d',
    'api_base': 'https://fhir-open.cerner.com/r4/ec2458f2-1e24-41c8-b71b-0e701af7583d',
    # 'api_base': 'https://fhir-open.cerner.com/dstu2',
    # 'api_base': 'https://r4.smarthealthit.org',
    # 'api_base': 'https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/DSTU2',
    'redirect_uri': 'http://localhost:8000/fhir-app/',
}

app = Flask(__name__)

# Flask-WTF requires an encryption key - the string can be anything
app.config['SECRET_KEY'] = 'C2HWGVoMGfNTBsrYQg8EcMrdTimkZfAb'

# Flask-Bootstrap requires this line
Bootstrap(app)


def _save_state(state):
    session['state'] = state

def _get_smart():

    state = session.get('state')
    if state:
        return client.FHIRClient(state=state, save_func=_save_state)
    else:
        smart = client.FHIRClient(settings=smart_defaults)

        import fhirclient.models.patient as p
        patient = p.Patient.read('12724067', smart.server)
        patient.birthDate.isostring
        # '1963-06-12'
        smart.human_name(patient.name[0])
        # 'Christy Ebert'

        return client.FHIRClient(settings=smart_defaults, save_func=_save_state)

def _logout():
    if 'state' in session:
        smart = _get_smart()
        smart.reset_patient()

def _reset():
    if 'state' in session:
        del session['state']

def _get_prescriptions(smart):
    bundle = MedicationRequest.where({'patient': smart.patient_id}).perform(smart.server)
    pres = [be.resource for be in bundle.entry] if bundle is not None and bundle.entry is not None else None
    if pres is not None and len(pres) > 0:
        return pres
    return None

def _get_medication_by_ref(ref, smart):
    med_id = ref.split("/")[1]
    return Medication.read(med_id, smart.server).code

def _med_name(med):
    if med.coding:
        name = next((coding.display for coding in med.coding if coding.system == 'http://www.nlm.nih.gov/research/umls/rxnorm'), None)
        if name:
            return name
    if med.text and med.text:
        return med.text
    return "Unnamed Medication(TM)"

def _get_med_name(prescription, client=None):
    if prescription.medicationCodeableConcept is not None:
        med = prescription.medicationCodeableConcept
        return _med_name(med)
    elif prescription.medicationReference is not None and client is not None:
        med = _get_medication_by_ref(prescription.medicationReference.reference, client)
        return _med_name(med)
    else:
        return 'Error: medication not found'


class NameForm(FlaskForm):
    name = StringField('', validators=[DataRequired()])
    submit = SubmitField('Find')

class Patient:
    def __init__(self, patient_id, name, birth_date, conditions):
        self.patient_id = patient_id
        self.name = name
        self.birth_date = birth_date
        self.conditions = conditions
        self.len_conditions = len(conditions)

class Condition:
    def __init__(self, id, name, recordedDate):
        self.id = id
        self.name = name
        self.recordedDate = recordedDate


# views

@app.route('/', methods=['GET', 'POST'])
def index():
    # names = get_names(ACTORS)
    names = ['Ken', 'Ella']
    # you must tell the variable 'form' what you named the class, above
    # 'form' is the variable name used in this template: index.html

    form = NameForm()
    body = "<br><h2>Results success!</h2><br>"
    # return body
    # return render_template('index.html', names=names, form=form, body=body)
    if form.validate_on_submit():
        name = form.name.data
        patients_template = []

        smart = client.FHIRClient(settings=smart_defaults)
        import fhirclient.models.patient as p

        search = p.Patient.where(struct={'_count': bytes('100', 'utf-8'), 'family': name})
        # search = p.Patient.where(struct={'family': name})
        patients = search.perform_resources(smart.server)
        # print(patients)
        cur_id_patient = 1
        for patient_this in patients:
            patient_id = patient_this.id.encode('ascii', 'ignore')
            import fhirclient.models.condition as condition
            search_condition = condition.Condition.where(struct={'patient': patient_id})
            # search_condition = condition.Condition.where(struct={'patient': '12724067'})
            conditions = search_condition.perform_resources(smart.server)
            print(conditions)
            conditions_template = []
            for condition_this in conditions:
                condition_id = condition_this.id.encode('ascii', 'ignore')
                recordedDate = "None"
                if condition_this.recordedDate is not None:
                    recordedDate = condition_this.recordedDate.isostring
                name = condition_this.code.text
                # print(recordedDate)
                conditions_template.append(Condition(condition_id, name, recordedDate))

            birth_date = "None"
            if patient_this.birthDate is not None:
                birth_date = patient_this.birthDate.isostring
            name = smart.human_name(patient_this.name[0])
            details = "<p>Patient details #{}<ul><li>ID: {}</li><li>Full Name: {}</li><li>Birth date: {}</li></ul>".format(
                cur_id_patient, patient_id, name, birth_date)
            print(details)
            body += details

            patients_template.append(Patient(patient_id, name, birth_date, conditions_template))
            cur_id_patient += 1

        # if name.lower() in names:
        #     # empty the form field
        #     form.name.data = ""
        #     # id = get_id(ACTORS, name)
        #     # # redirect the browser to another route and template
        #     # return redirect( url_for('actor', id=id) )
        # else:
        #     body += "That actor is not in our database."
        return render_template('index.html', names=names, form=form,
                               patients=patients_template, len_patients=len(patients_template))
    else:
        return render_template('index.html', names=names, form=form,
                               patients=[], len_patients=0)

#
# @app.route('/')
# @app.route('/index.html')
# def index():
#     body = "<h1>Hello</h1>"
#     smart = client.FHIRClient(settings=smart_defaults)
#
#     import fhirclient.models.patient as p
#     patient = p.Patient.read('12724067', smart.server)
#
#     patient_id = patient.id.encode('ascii', 'ignore')
#     birth_date = patient.birthDate.isostring
#     name = smart.human_name(patient.name[0])
#     details = "<p>Patient details<ul><li>ID: {}</li><li>Full Name: {}</li><li>Birth date: {}</li></ul>".format(patient_id, name, birth_date)
#     print(details)
#
#     body += details
#
#     search = p.Patient.where(struct={'_count': '23', 'family': 'Smith'})
#     # search = p.Patient.where(struct={'family': 'Smith', 'gender': 'female'})
#     patients = search.perform_resources(smart.server)
#     # print(patients)
#     cur_id_patient = 1
#     for patient_this in patients:
#         patient_id = patient_this.id.encode('ascii', 'ignore')
#         birth_date = "None"
#         if patient_this.birthDate is not None:
#             birth_date = patient_this.birthDate.isostring
#         name = smart.human_name(patient_this.name[0])
#         details = "<p>Patient details #{}<ul><li>ID: {}</li><li>Full Name: {}</li><li>Birth date: {}</li></ul>".format(cur_id_patient, patient_id, name, birth_date)
#         print(details)
#         body += details
#         cur_id_patient += 1

    # import fhirclient.models.procedure as p
    # search = p.Procedure.where(struct={'subject': 'f001', 'status': 'completed'})
    # procedures = search.perform_resources(smart.server)
    # for procedure in procedures:
    #     body += "<p>Procedure details<ul><li>Full Name: " + name + "</li><li>Birth date: " + birth_date + "</li></ul>"
    #
    # """ The app's main page.
    # """
    # smart = _get_smart()
    # body = "<h1>Hello</h1>"
    #
    # if smart.ready and smart.patient is not None:       # "ready" may be true but the access token may have expired, making smart.patient = None
    #     name = smart.human_name(smart.patient.name[0] if smart.patient.name and len(smart.patient.name) > 0 else 'Unknown')
    #
    #     # generate simple body text
    #     body += "<p>You are authorized and ready to make API requests for <em>{0}</em>.</p>".format(name)
    #     pres = _get_prescriptions(smart)
    #     if pres is not None:
    #         body += "<p>{0} prescriptions: <ul><li>{1}</li></ul></p>".format("His" if 'male' == smart.patient.gender else "Her", '</li><li>'.join([_get_med_name(p,smart) for p in pres]))
    #     else:
    #         body += "<p>(There are no prescriptions for {0})</p>".format("him" if 'male' == smart.patient.gender else "her")
    #     body += """<p><a href="/logout">Change patient</a></p>"""
    # else:
    #     auth_url = smart.authorize_url
    #     if auth_url is not None:
    #         body += """<p>Please <a href="{0}">authorize</a>.</p>""".format(auth_url)
    #     else:
    #         body += """<p>Running against a no-auth server, nothing to demo here. """
    #     body += """<p><a href="/reset" style="font-size:small;">Reset</a></p>"""
# return body


@app.route('/fhir-app/')
def callback():
    """ OAuth2 callback interception.
    """
    smart = _get_smart()
    try:
        smart.handle_callback(request.url)
    except Exception as e:
        return """<h1>Authorization Error</h1><p>{0}</p><p><a href="/">Start over</a></p>""".format(e)
    return redirect('/')


@app.route('/logout')
def logout():
    _logout()
    return redirect('/')


@app.route('/reset')
def reset():
    _reset()
    return redirect('/')


# start the app
if '__main__' == __name__:
    # import flaskbeaker
    # flaskbeaker.FlaskBeaker.setup_app(app)
    
    logging.basicConfig(level=logging.DEBUG)

    # replit.com
    # app.run(host='0.0.0.0', port=8080)
    app.run(debug=True, port=8000)
