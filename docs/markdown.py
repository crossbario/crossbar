# coding=utf8

import os
import re
import copy
import subprocess

from pygments import highlight
from pygments.lexers import get_lexer_by_name
from pygments.formatters import HtmlFormatter

import mistune


def get_git_latest_commit(gitdir = None):
   """
   Get git info line on latest commit.

   E.g.: Jay Martin (Wed Aug 13 07:46:39 2014 -0700): Updated Router Realms (markdown)

   Usage: env['COMMIT'] = env.GetLatestCommit()
   """
   gitdir = gitdir or '.git'
   cmd = 'git --git-dir="{}" log -1 --pretty=format:"%an (%ad): %s"'.format(gitdir)
   output = subprocess.check_output(cmd, shell = True).strip()
   return output


class MyInlineGrammar(mistune.InlineGrammar):
    # it would take a while for creating the right regex
    wiki_link = re.compile(
        r'\[\['                   # [[
        r'([\s\S]+?\|[\s\S]+?)'   # Page 2|Page 2
        r'\]\](?!\])'             # ]]
    )

    wiki_short_link = re.compile(
        r'\[\['                   # [[
        r'([\s\S]+?)'             # Page 2
        r'\]\](?!\])'             # ]]
    )


class MyInlineLexer(mistune.InlineLexer):
    default_rules = copy.copy(mistune.InlineLexer.default_rules)

    # Add wiki_link parser to default features
    # you can insert it any place you like
    default_rules.insert(3, 'wiki_link')
    default_rules.insert(3, 'wiki_short_link')

    def __init__(self, renderer, rules=None, **kwargs):
        if rules is None:
            # use the inline grammar
            rules = MyInlineGrammar()

        super(MyInlineLexer, self).__init__(renderer, rules, **kwargs)

    def output_wiki_link(self, m):
        text = m.group(1)
        alt, link = text.split('|')
        # you can create an custom render
        # you can also return the html if you like
        return self.renderer.wiki_link(alt, link)

    def output_wiki_short_link(self, m):
        text = m.group(1)
        alt, link = text, text
        # you can create an custom render
        # you can also return the html if you like
        return self.renderer.wiki_link(alt, link)


HEADER_PAT_REGEX = r"^[a-zA-Z0-9_,\-\?\. ]*$"
HEADER_PAT = re.compile(HEADER_PAT_REGEX)

class DocPageRenderer(mistune.Renderer):

   def __init__(self, pages, debug = False):
      mistune.Renderer.__init__(self)
      self.debug = debug
      self._pages = pages
      self._prefix = None

   def header(self, text, level, raw=None):
      if not HEADER_PAT.match(raw):
         print("invalid header (does not match pattern {}): {}".format(HEADER_PAT_REGEX, raw))
      if text != raw:
         print("invalid header: {}".format(raw))
      if True: # render anchors besides headline elements
         anchor = text.lower().strip().replace(' ', '-')
         res = u"""<h{level} id="{anchor}">{text}<a class="headerlink" title="Permalink to this headline" href="#{anchor}">¶</a></h{level}>""".format(level=level, text=text, anchor=anchor)
      else:
         res = mistune.Renderer.header(self, text, level, raw)
      return res

   def wiki_link(self, alt, link):
      if self._prefix:
         return '<a href="{}/{}">{}</a>'.format(self._prefix, link.replace(' ', '-'), alt)
      else:
         return '<a href="{}">{}</a>'.format(link.replace(' ', '-'), alt)

   def block_code(self, code, lang):
      if self.debug:
         print "CODE", lang, len(code)

      lexer = None
      if lang:
         try:
            lexer = get_lexer_by_name(lang, stripall = True)
         except:
            print("failed to load lexer for language '{}'".format(lang))

      if not lexer:
         return "\n<pre><code>{}</code></pre>\n".format(mistune.escape(code))

      formatter = HtmlFormatter()
      return '\n<div class="highlight-code">{}</div>\n'.format(highlight(code, lexer, formatter))

   def autolink(self, link, is_email = False):
      if self.debug:
         print "autolink", link
      return mistune.Renderer.autolink(self, link, is_email)

   def codespan(self, text):
      if self.debug:
         print "codespan", text
      return mistune.Renderer.codespan(self, text)

   def link(self, link, title, content):
      if not (link.startswith('http') or link.startswith('/') or link.startswith('#')):
         if self._prefix:
            link = "{}/{}/".format(self._prefix, link.replace(' ', '-'))
         else:
            link = "{}/".format(link.replace(' ', '-'))

      if self.debug:
         print "link", link, title, content
      return mistune.Renderer.link(self, link, title, content)


class DocPages:
   def __init__(self, docroot, extensions = ['.md'], debug = False):
      rend = DocPageRenderer(self, debug)
      inline = MyInlineLexer(rend)
      self._renderer = mistune.Markdown(renderer = rend, inline = inline)
      self._pages = {}
      self.debug = debug

      total = 0
      errors = 0

      for dirpath, dirnames, filenames in os.walk(docroot):
         for f in filenames:
            base, ext = os.path.splitext(f)
            if ext in extensions:
               total += 1
               fp = os.path.join(dirpath, f)
               with open(fp, 'r') as fd:
                  source = fd.read()
                  try:
                     if self.debug:
                        print "\nprocessing {}".format(fp)
                     if base == 'Home':
                        rend._prefix = None
                     else:
                        rend._prefix = '..'
                     contents = self._renderer(source)
                  except Exception as e:
                     print "warning: failed to process {}: {}".format(fp, e)
                     errors += 1
                  else:
                     path = base
                     self._pages[base] = contents
      print("processed {} files: {} ok, {} error".format(total, len(self._pages), errors))

      #self._pages[None] = self._pages[index]

   def render(self, path):
      return self._pages.get(path, None)

