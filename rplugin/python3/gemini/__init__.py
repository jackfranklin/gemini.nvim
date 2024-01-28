import os
from typing import List
import re

import pynvim
from pynvim.api import Nvim
import sqlite3
import google.generativeai as genai

# Set up the model
generation_config = {
  'temperature': 0.3,
  'top_p': 0.6,
  'top_k': 100,
  'max_output_tokens': 2048,
}

safety_settings = [
  {
    'category': 'HARM_CATEGORY_HARASSMENT',
    'threshold': 'BLOCK_MEDIUM_AND_ABOVE'
  },
  {
    'category': 'HARM_CATEGORY_HATE_SPEECH',
    'threshold': 'BLOCK_MEDIUM_AND_ABOVE'
  },
  {
    'category': 'HARM_CATEGORY_SEXUALLY_EXPLICIT',
    'threshold': 'BLOCK_MEDIUM_AND_ABOVE'
  },
  {
    'category': 'HARM_CATEGORY_DANGEROUS_CONTENT',
    'threshold': 'BLOCK_MEDIUM_AND_ABOVE'
  },
]

current_dir = os.path.dirname(os.path.abspath(__file__))
plugin_root = os.path.join(current_dir, '..', '..', '..')
db_path = os.path.join(plugin_root, 'gemini.db')


def setup_sqlite():
  con = sqlite3.connect(db_path)
  cur = con.cursor()
  cur.execute("""
  CREATE TABLE IF NOT EXISTS gemini_chat(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request TEXT NOT NULL,
    response TEXT NOT NULL,
    t TIMESTAMP DEFAULT CURRENT_TIMESTAMP
  )
  """)
  con.close()


def insert_chat(request: str, response: str):
  con = sqlite3.connect(db_path)
  cur = con.cursor()
  data = (
    request,
    response,
  )
  cur.execute("""
  INSERT INTO gemini_chat(request, response) VALUES(?, ?)
  """, data)
  con.commit()
  con.close()


@pynvim.plugin
class GeminiPlugin(object):

  def __init__(self, nvim: Nvim):
    self.nvim = nvim

    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
      self.nvim.request('nvim_notify', 'GEMINI_API_KEY not set', 3, {})
      return

    genai.configure(api_key=api_key)

    self.model = genai.GenerativeModel(
      model_name='gemini-pro',
      generation_config=generation_config,
      safety_settings=safety_settings,
    )

    self._setup_module()

    setup_sqlite()
    # self.nvim.request('nvim_notify', 'GenerativeModel setup.', 2, {})

  def _setup_module(self):
    self.nvim.exec_lua("_gemini_plugin = require('gemini')")
    self.module = self.nvim.lua._gemini_plugin

  def _check_setup(self):
    return hasattr(self, 'model')

  @pynvim.function('_gemini_api_stream_async', sync=False)
  def async_api_call_stream(self, args: List):
    if not self._check_setup():
      return

    if len(args) != 3:
      return
    if not isinstance(args[0], int):
      return
    if not isinstance(args[1], int):
      return
    if not isinstance(args[2], str):
      return

    bufnr = args[0]
    win_id = args[1]
    request = args[2]

    try:
      self.nvim.request('nvim_buf_set_lines', bufnr, 0, -1, False, ['Generating...'])
      prompt_parts = [request + '\n']
      response = self.model.generate_content(prompt_parts, stream=True)
      current = ''
      for chunk in response:
        current += chunk.text
        self.nvim.request('nvim_buf_set_lines', bufnr, 0, -1, False, current.split('\n'))
        current_win = self.nvim.request('nvim_get_current_win')
        if current_win.handle == win_id:
          self.nvim.request('nvim_feedkeys', 'G$', 'n', False)

      self.nvim.request('nvim_echo', [['gemini done.']], True, {})
      insert_chat(request, current)

      self.module.handle_async_callback(dict(
        result=current,
        win_id=win_id,
        bufnr=bufnr,
      ))
    except Exception:
      pass

  @pynvim.function('_gemini_api', sync=True)
  def api_call(self, args: List) -> str:
    if not self._check_setup():
      return

    if len(args) != 1 or not isinstance(args[0], str):
      return

    request = args[0]
    prompt_parts = [request + '\n']
    try:
      response = self.model.generate_content(prompt_parts)
      result = response.text
      insert_chat(request, result)
      return result
    except Exception:
      return ''

  @pynvim.function('_gemini_api_async', sync=False)
  def async_api_call(self, args: List):
    if not self._check_setup():
      return

    if len(args) != 2:
      return
    if not isinstance(args[0], dict):
      return
    if not isinstance(args[1], str):
      return

    context = args[0]
    win_id = context['win_id']
    pos = context['pos']
    callback = context.get('callback', None)
    extract_code = context.get('extract_code', False)
    request = args[1]
    prompt_parts = [request + '\n']

    try:
      response = self.model.generate_content(prompt_parts, stream=True)
      result = ''
      for chunk in response:
        result += chunk.text

      if extract_code:
        pattern = r'^```(?:\w+)?\s*\n(.*?)(?=^```)```'
        search_result = re.findall(pattern, result, re.DOTALL | re.MULTILINE)
        if len(search_result) > 0:
          result = search_result[0]

      self.module.handle_async_callback({
        'result': result,
        'win_id': win_id,
        'row': pos[0],
        'col': pos[1],
        'callback': callback,
      })

      insert_chat(request, result)
    except Exception as e:
      self.nvim.request('nvim_echo', [[str(e)]], True, {})
      pass

  @pynvim.function('_generative_ai_list_models', sync=True)
  def list_models(self, args: List):
    if not self._check_setup():
      return

    models = genai.list_models()
    results = []
    for model in models:
      results.append(
        dict(name=model.name, supported_generation_methods=model.supported_generation_methods))
    return results
