#! /usr/bin/python3
# -*- coding: utf-8 -*-

import gevent
from gevent import monkey
monkey.patch_all()
from gevent.pool import Pool, Timeout

from math import ceil
from string import Template

import os
from ebooklib import epub
import pytumblr
import sys
import shutil
import time

from urllib.request import urlopen

from secret import tumblr_api_key
client = pytumblr.TumblrRestClient(tumblr_api_key)

compress_images_too = True
if shutil.which('7z') is None:
    compress_images_too = False
    print('I couldn\'t find 7z. You will put images into the book yourself.')


# blog_name = sys.argv[-1]
blog_name = 'yourplayersaidwhat'

blog_info = client.blog_info(blog_name)
info = blog_info['blog']

info['title'] = info['title'].strip()
info['updated'] = time.ctime(int(info['updated']))
info['pages'] = int(ceil(info['posts'] / 20.))

info['pdirname'] = info['name'] + '_pic_cache'

pdirname = info['pdirname']
try:
    os.mkdir(pdirname)
except:
    pass

print('** {} **\n\n{} posts\n{} pages'.format(info['name'], info['posts'], info['pages']))


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

# info['pages'] = 1
# print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! Remove pages restriction')

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
# for url in pictures_links:
#     picname = os.path.basename(url).replace('_', '-')
#     img = epub.EpubImage(
#         file_name=pdirname + os.sep + picname,
#         content=open(pdirname + os.sep + picname, 'rb').read())
#     book.add_item(img)




chapter_size = 200

chapter = ''
chapter_num = 0
real_posts_count = len(posts)

posts += [{'type':'pass'}] * (chapter_size - (len(posts) % chapter_size) + 1)
ids_for_spine = list()

for i, post in enumerate(posts):

    if post['type'] == 'photo':
        pp = ''
        for photo in post['photos']:
            purl = photo['original_size']['url']
            pn = os.path.basename(purl).replace('_', '-')

            photo['picturename'] = pn
            photo['pdirname'] = pdirname
            pp += templates['picture'].substitute(**photo)

        post['parsedphotos'] = pp
        post['picscount'] = '{} picture'.format(len(post['photos']))
        if len(post['photos']) > 1: post['picscount'] += 's'

    if post['type'] == 'answer':
        if post['summary'] is None:
            post['summary'] = 'There was no title'

    if not post['type'] == 'pass':
        post['postnumber'] = str(i + 1)
        if 'title' in post.keys() and post['title'] is None:
            post['title'] = 'There was no title'
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

last_chap_link = book.toc[-1]
book.toc = book.toc[:-1]
book.toc += (epub.Link(
    last_chap_link.href,
    '{} - {}'.format(last_chap_link.title.split(' ')[0], real_posts_count),
    last_chap_link.uid), )

book.spine = ['nav', introchapter.id] + ids_for_spine

book.add_item(epub.EpubNcx())
book.add_item(epub.EpubNav())

bookname = info['name'] + '.epub'
epub.write_epub(bookname, book, {})


if compress_images_too:
    # dirty hack
    os.mkdir('EPUB')
    shutil.copytree(pdirname, 'EPUB/images')
    os.system('7z a -tzip {0} EPUB/images/*'''.format(bookname, pdirname))
    shutil.rmtree('EPUB')
    shutil.move(bookname + '.tmp', bookname)
else:
    print('Rename {} into images/ and put it into {}/EPUB/images. I warned you:)'.format(pdirname, bookname))
