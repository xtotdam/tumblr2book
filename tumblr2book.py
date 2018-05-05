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
from ebooklib import epub
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

info['pdirname'] = pdirname

print('** {} **\n\n{} posts\n{} pages'.format(blog_name, info['posts'], info['pages']))


book = epub.EpubBook()
book.set_title(info['title'])
book.add_author(info['title'])
book.add_author('Tumblr2book')
book.set_language('en')

introchapter = epub.EpubHtml(file_name='intro.xhtml')
introchapter.content = '''
<h1> {} </h1>
<p> {} </p>
<p> {} posts </p>
<p> Blog last updated {} </p>
<p> Scraped {} </p>
'''.format(info['title'], info['description'], info['posts'], info['updated'], time.ctime())
book.add_item(introchapter)


templates = {
    'header': Template(open('header.tmpl').read()),
    'picture': Template(open('picture.tmpl').read()),

    'text': Template(open('text.tmpl').read()),
    'quote': Template(open('quote.tmpl').read()),
    'link': Template(open('link.tmpl').read()),
    'answer': Template(open('answer.tmpl').read()),
    'video': Template(open('video.tmpl').read()),
    'audio': Template(open('audio.tmpl').read()),
    'photo': Template(open('photo.tmpl').read()),
    'chat': Template(open('chat.tmpl').read()),
}

# info['pages'] = 25

pool = Pool(5)
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
        print('\nReclaiming ' + str(len(pages_to_fetch)) + ' timeoutted pages')

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

# does this even work?
for url in pictures_links:
    picname = os.path.basename(url).replace('_', '-')
    img = epub.EpubImage(filename='images/' + picname, content=pdirname + os.sep + picname)
    book.add_item(img)




chapter_size = 500

chapter = ''
chapter_num = 0

posts += [{'type':'pass'}] * (chapter_size - (len(posts) % chapter_size) + 1)
ids_for_spine = list()

for i, post in enumerate(posts):

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

    if not post['type'] == 'pass':
        post['header'] = templates['header'].substitute(**post)
        processed_post = templates[post['type']].substitute(**post)

        chapter += processed_post

    if not (i + 1) % chapter_size:
        c = epub.EpubHtml(file_name='chap_{:04d}.xhtml'.format(chapter_num))
        c.content = chapter
        book.add_item(c)
        ids_for_spine.append(c.id)

        chapter = ''
        chapter_num += 1

book.toc = (epub.Link('intro.xhtml', 'Introduction', 'intro'), )
book.toc += tuple(epub.Link(
    'chap_{:04d}.xhtml'.format(n),
    '{} - {}'.format(n * chapter_size + 1, (n + 1) * chapter_size),
    str(n)) for n in range(len(posts) // chapter_size))

book.spine = ['nav', 'intro'] + ids_for_spine

book.add_item(epub.EpubNcx())
book.add_item(epub.EpubNav())

epub.write_epub('test.epub', book, {})
