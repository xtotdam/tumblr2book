#! /usr/bin/python3
# -*- coding: utf-8 -*-

from math import ceil
import pytumblr
import sys
import time
from pprint import pprint
import json
import requests

import html2text
import html

from string import Template

import re
import os

pdirname = 'pictures'
try:
    os.mkdir(pdirname)
except:
    pass


from secret import tumblr_api_key
client = pytumblr.TumblrRestClient(tumblr_api_key)


# blog = sys.argv[-1]
blog_name = 'yourplayersaidwhat'

blog_info = client.blog_info(blog_name)
info = blog_info['blog']

info['title'] = info['title'].strip()
info['updated'] = time.ctime(int(info['updated']))
info['pages'] = int(ceil(info['posts'] / 20.))

d = html2text.html2text(info['description'])
d = (s.strip() for s in d.split('\n'))
d = (s if s else '\n' for s in d)
d = '\n'.join(d)
d = d.replace('\n\n', '\n\\\\\n').replace('\n', ' ')
d = re.sub(r'\[(.*?)\]\((.*?)\)', r'\\href{\2}{\1}', d)

info['description'] = d
info['pdirname'] = pdirname

with open('main.tex', 'w', encoding='utf8') as f:
    maindoc = Template(open('book.tmpl').read())
    f.write(maindoc.substitute(**info))


templates = {
    'text': Template(open('text.tmpl').read()),
    'quote': Template(open('quote.tmpl').read()),
    'link': Template(open('link.tmpl').read()),
    'answer': Template(open('answer.tmpl').read()),
    'video': Template(open('video.tmpl').read()),
    'audio': Template(open('audio.tmpl').read()),
    'photo': Template(open('photo.tmpl').read()),
    'picture': Template(open('picture.tmpl').read()),
    'chat': Template(open('chat.tmpl').read()),
}

print()
with open('temp_posts.txt', 'w', encoding='utf8') as f:

    # for i in range(info['pages']):
    for i in range(25):

        posts = client.posts(blog_name, offset=20 * i)['posts']

        for post in posts:
            print(post['type'] + ' ', end='')

            if post['type'] == 'text':
                post['body'] = html.unescape(post['body'])
                if post['title']:
                    post['title'] = html.unescape(post['title'])

            if post['type'] == 'quote':
                post['text'] = html.unescape(post['text'])
                post['source'] = html.unescape(post['source'])

            if post['type'] == 'chat':
                post['body'] = post['body'].replace('\n', '\n\n')

            if post['type'] == 'photo':
                pp = ''
                for photo in post['photos']:
                    purl = photo['original_size']['url']
                    pn = os.path.basename(purl).replace('_', '-')

                    if not os.path.exists(pdirname + os.sep + pn):
                        print('p', end='')
                        r = requests.get(purl, timeout=(5, 20))
                        if r.status_code == 200:
                            with open(pdirname + os.sep + pn, 'wb') as fp:
                                fp.write(r.content)
                    else:
                        print('s', end='')

                    photo['picturename'] = pn
                    pp += templates['picture'].substitute(**photo)

                post['parsedphotos'] = pp
                post['picscount'] = '{} picture'.format(len(post['photos']))
                if len(post['photos']) > 1: post['picscount'] += 's'

            f.write(templates[post['type']].substitute(**post))

        print('page %d of %d ' % (i, info['pages']))
