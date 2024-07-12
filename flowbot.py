from quart import Quart, render_template
from quart_cors import cors

from functions.bots import bots_bp
from functions.intents import intents_bp
from functions.rules import rules_bp
from functions.stories import stories_bp
from functions.slots import slots_bp
from functions.entities import entities_bp
from functions.lookup import lookup_bp
from functions.responses import responses_bp
from functions.actions import actions_bp
from functions.models import models_bp
from functions.generative import generative_bp
from functions.tokens import tokens_bp
from functions.chats import chats_bp

app = Quart(__name__)
app.json.sort_keys = False # Not sort JSONify results alphabetically
app = cors(app, allow_origin = "*")

app.register_blueprint(bots_bp, url_prefix='/bots')
app.register_blueprint(intents_bp, url_prefix='/intents')
app.register_blueprint(rules_bp, url_prefix='/rules')
app.register_blueprint(stories_bp, url_prefix='/stories')
app.register_blueprint(slots_bp, url_prefix='/slots')
app.register_blueprint(entities_bp, url_prefix='/entities')
app.register_blueprint(lookup_bp, url_prefix='/lookup')
app.register_blueprint(responses_bp, url_prefix='/responses')
app.register_blueprint(actions_bp, url_prefix='/actions')
app.register_blueprint(models_bp, url_prefix='/models')
app.register_blueprint(generative_bp, url_prefix='/generative')
app.register_blueprint(tokens_bp, url_prefix='/tokens')
app.register_blueprint(chats_bp, url_prefix='/chats')

@app.route('/', methods=['GET'])
async def index():
    return await render_template('index.html')

if __name__ == '__main__':
    app.run()