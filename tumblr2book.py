#! /usr/bin/python3
# -*- coding: utf-8 -*-

import gevent
from gevent import monkey
monkey.patch_all()
from gevent.pool import Pool, Timeout

from functools import partial
from math import ceil
from pprint import pprint, pformat
from string import Template

import html
import html2text
import json
import os
import pytumblr
import re
import sys
import time

from urllib.request import urlopen

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

print('** {} **\n\n{} posts\n{} pages'.format(blog_name, info['posts'], info['pages']))

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





# info['pages'] = 100


pool = Pool(3)
pages_to_fetch = range(info['pages'])
big_posts_dict = dict()
pages_without_posts = list()
ptf = []

def fetch_posts_page(page):
    print('Getting page #', page + 1, 'of', info['pages'], end='\r')
    sys.stdout.flush()
    try:
        with Timeout(5):
            response = client.posts(blog_name, offset=20 * page)
            big_posts_dict[page] = response['posts']
    except KeyError:
        if 'errors' in response.keys():
            ptf.append(page)
        else:
            print(page, response)
            big_posts_dict[page] = []
            pages_without_posts.append(page)
    except Timeout:
        ptf.append(page)

while pages_to_fetch:
    pool.map(fetch_posts_page, pages_to_fetch)
    pages_to_fetch = ptf[:]
    ptf = []
    if pages_to_fetch:
        print('\nReclaiming timeoutted pages')

posts = list()
for page in range(info['pages']):
    posts += big_posts_dict[page]

print('\n', len(posts), 'posts got')
print(len(pages_without_posts), 'pages without posts:', sorted(pages_without_posts))





pictures_links = list()
for post in posts:
    if post['type'] == 'photo':
        for photo in post['photos']:
            pictures_links.append(photo['original_size']['url'])

print ('We will download', len(pictures_links), 'pics')

ptf = list()

def fetch_pic(url):
    picname = os.path.basename(url).replace('_', '-')

    if not os.path.exists(pdirname + os.sep + picname):
        print('+', end='')
        try:
            with Timeout(15):
                data = urlopen(url).read()
                with open(pdirname + os.sep + picname, 'wb') as fp:
                    fp.write(data)
        except Timeout:
            ptf.append(url)
    else:
        print('-', end='')

while pictures_links:
    pool.map(fetch_pic, pictures_links)
    pictures_links = ptf[:]
    ptf = []
    if pictures_links:
        print('\nReclaiming timeoutted pics')

print ('\nGot \'em')





with open('temp_posts.txt', 'w', encoding='utf8') as f:
    for post in posts:

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

                photo['picturename'] = pn
                pp += templates['picture'].substitute(**photo)

            post['parsedphotos'] = pp
            post['picscount'] = '{} picture'.format(len(post['photos']))
            if len(post['photos']) > 1: post['picscount'] += 's'

        f.write(templates[post['type']].substitute(**post))


