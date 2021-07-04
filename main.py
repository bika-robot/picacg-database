
# 一本书
import base64
import sqlite3
import threading
import time
from _md5 import md5
from queue import Queue
from random import random, randint
from urllib import parse
import pickle

import requests

from src.server import Server, req, json, config, Log
from langconv import Converter
from conf.baidu import BaiduAppId, BaiduKey

class DbBook(object):
    def __init__(self):
        self.id = ""             # 唯一标识
        self.title = ""           # 标题
        self.title2 = ""          # 标题2
        self.author = ""          # 作者
        self.chineseTeam = ""     # 汉化组
        self.description = ""     # 描述
        self.epsCount = 0         # 章节数
        self.pages = 0            # 页数
        self.finished = False     # 是否完本
        self.categories = ""      # 分类
        self.tags = ""            # tag
        self.likesCount = 0       # 爱心数
        self.created_at = 0       # 创建时间
        self.updated_at = 0       # 更新时间
        self.path = ""            # 路径
        self.fileServer = ""             # 路径
        self.originalName = ""    # 封面名
        self.totalLikes = 0        #
        self.totalViews = 0        #


class MainInfo(object):
    def __init__(self):
        self.url = "http://api.fanyi.baidu.com/api/trans/vip/translate"
        self.appid = BaiduAppId
        self.secretKey = BaiduKey
        self.fromLang = 'jp'
        self.toLang = "zh"

        self._inQueue = Queue()
        self._resultQueue = Queue()

        self.checkPage = 2
        self.categoryIndex = 0
        self.count = 0
        self.idToCateGoryBase = []
        self.thread = threading.Thread(target=self.Run)
        self.thread.setDaemon(True)
        self.conn = sqlite3.connect("data/book.db")
        self.cur = self.conn.cursor()
        self.cur.execute("select * from book")
        self.books = {}
        self._needUpIds = set()
        self._updateIds = {}
        for data in self.cur.fetchall():
            info = DbBook()
            info.id = data[0]
            info.title = data[1]
            info.title2 = data[2]
            info.author = data[3]
            info.chineseTeam = data[4]
            info.description = data[5]
            info.epsCount = data[6]
            info.pages = data[7]
            info.finished = data[8]
            info.likesCount = data[9]
            info.categories = data[10]
            info.tags = data[11]
            info.created_at = data[12]
            info.updated_at = data[13]
            info.path = data[14]
            info.fileServer = data[15]
            info.originalName = data[16]
            info.totalLikes = data[17]
            info.totalViews = data[18]
            self.books[info.id] = info

    def AddHistory(self, book):
        assert isinstance(book, DbBook)
        sql = "replace INTO book(id, title, title2, author, chineseTeam, description, epsCount, pages, finished, likesCount, categories, tags," \
              "created_at, updated_at, path, fileServer, originalName, totalLikes, totalViews) " \
              "VALUES ('{0}', '{1}', '{2}', '{3}', '{4}', '{5}', {6}, {7}, {8}, {9}, '{10}', '{11}', '{12}', '{13}', '{14}', '{15}', '{16}', {17}, {18}); " \
            .format(book.id, book.title, book.title2, book.author, book.chineseTeam, book.description, book.epsCount, book.pages, int(book.finished), book.likesCount,
                   book.categories, book.tags, book.created_at, book.updated_at, book.path, book.fileServer, book.originalName, book.totalLikes, book.totalViews)
        sql = sql.replace("\0", "")
        # day = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))
        fileName = time.strftime('%Y-%m-%d', time.localtime(time.time()))
        SubVersion = int(time.time())
        # sql2 = "replace INTO system(id, size, time, subversion) VALUES('{0}', {1}, '{2}', {3})".format(
        #     config.UpdateVersion, len(self.books), day, SubVersion
        # )
        try:
            self.cur.execute(sql)
            # self.cur.execute(sql2)
            data = base64.b64encode(sql.encode("utf-8")).decode("utf-8")
            info =  base64.b64encode(pickle.dumps(book)).decode("utf-8")
            with open("data/"+fileName+".data", "a") as f:
                f.write(info + "\r\n")
            with open("version.txt", "w") as f2:
                f2.write(str(SubVersion))
        except Exception as es:
            Log.Error(es)
        return

    # def LoadNextPage(self, page, maxPage):
    #     if page >= maxPage:
    #         return maxPage
    #     print("load page: " + str(page) + "/" + str(maxPage))
    #     task = Server().Send(req.AdvancedSearchReq(page, [], "dd"), isASync=False)
    #     if hasattr(task.res, "raw"):
    #         return self.SendSearchBack(page, task.res.raw.text)
    #     return page + 1

    def LoadNextPage2(self, categoryIndex, page, maxPage):
        if page > maxPage or page >= self.checkPage:
            categoryIndex += 1
            if categoryIndex >= len(self.idToCateGoryBase):
                Log.Info("end")
                return categoryIndex, page+1, maxPage
            else:
                page = 1
                maxPage = 1
        title = self.idToCateGoryBase[categoryIndex]
        Log.Info("load page {}: ".format(title) + str(page) + "/" + str(maxPage) + " " + str(categoryIndex) + "/" + str(len(self.idToCateGoryBase)))
        task = Server().Send(req.CategoriesSearchReq(page, title, "dd"), isASync=False)
        if hasattr(task.res, "raw"):
            page, maxPage = self.SendSearchBack(page, maxPage, task.res.raw.text)
        return categoryIndex, page+1, maxPage

    def SendSearchBack(self, page, maxPage, raw):
        try:
            data = json.loads(raw)
            if data.get("code") == 200:
                info = data.get("data").get("comics")
                page = int(info.get("page"))
                pages = int(info.get("pages"))
                for v in info.get("docs", []):
                    a = DbBook()
                    a.id = v.get('_id')
                    a.title = v.get('title', "").replace("'", " ").replace("\"", " ")
                    a.author = v.get('author', "").replace("'", " ").replace("\"", " ")
                    a.chineseTeam = v.get('chineseTeam', "").replace("'", " ").replace("\"", " ")
                    a.description = v.get('description', "").replace("'", " ").replace("\"", " ")
                    a.finished = v.get('finished')
                    a.categories = v.get('categories', [])
                    a.tags = v.get('tags', [])
                    a.likesCount = v.get('likesCount', 0)
                    a.created_at = v.get('created_at', "")
                    a.updated_at = v.get('updated_at', "")
                    a.path = v.get('thumb', {}).get("path")
                    a.fileServer = v.get('thumb', {}).get("fileServer")
                    a.originalName = v.get('thumb', {}).get("originalName", "").replace("'", " ").replace("\"", " ")
                    a.pages = v.get('pagesCount', 0)
                    a.epsCount = v.get('epsCount', 0)
                    # self.books[a.id] = a
                    # self.AddHistory(a)
                    self._needUpIds.add(a.id)
                return page + 1, pages
            else:
                return page + 1, maxPage
        except Exception as es:
            return page + 1, maxPage

    # def LoadRandomNextPage(self):
    #     task = Server().Send(req.GetRandomReq(), isASync=False)
    #     if hasattr(task.res, "raw"):
    #         return self.SendRandomBack(task.res.raw.text)
    #     return
    #
    # def SendRandomBack(self, raw):
    #     try:
    #         data = json.loads(raw)
    #         if data.get("code") == 200:
    #             for v in data.get("data").get('comics', []):
    #                 if v.get("_id") in self.books:
    #                     continue
    #                 a = Book()
    #                 a.id = v.get('_id')
    #                 a.title = v.get('title', "").replace("'", "\"").replace("/"", " " ")
    #                 a.author = v.get('author', "").replace("'", "\"").replace("/"", " " ")
    #                 a.chineseTeam = v.get('chineseTeam', "").replace("'", "\"").replace("/"", " " ")
    #                 a.description = v.get('description', "").replace("'", "\"").replace("/"", " " ")
    #                 a.finished = v.get('finished')
    #                 a.categories = v.get('categories', [])
    #                 a.tags = v.get('tags', [])
    #                 a.likesCount = v.get('likesCount', 0)
    #                 a.created_at = v.get('created_at', "")
    #                 a.updated_at = v.get('updated_at', "")
    #                 a.path = v.get('thumb', {}).get("path")
    #                 a.fileServer = v.get('thumb', {}).get("fileServer")
    #                 a.originalName = v.get('thumb', {}).get("originalName").replace("/"", " " ")
    #                 a.pages = v.get('pagesCount', 0)
    #                 a.epsCount = v.get('epsCount', 0)
    #                 self.books[a.id] = a
    #                 # self.AddHistory(a)
    #                 self._resultQueue.put(a.id)
    #             return
    #         else:
    #             return
    #     except Exception as es:
    #         return

    def OpenBookBack(self, raw):
        try:
            data = json.loads(raw)
            if data.get("code") == 200:
                if data.get("data").get("comic"):
                    info = data['data']['comic']
                    bookInfo = DbBook()
                    bookInfo.id = info.get("_id")

                    bookInfo.description = Converter('zh-hans').convert(info.get("description", "")).replace("'", "\"")
                    bookInfo.created_at = info.get("created_at")
                    bookInfo.updated_at = info.get("updated_at")
                    bookInfo.chineseTeam = Converter('zh-hans').convert(info.get("chineseTeam", "")).replace("'", "\"")
                    bookInfo.author = Converter('zh-hans').convert(info.get("author", "")).replace("'", "\"")
                    bookInfo.finished = info.get("finished")
                    bookInfo.likesCount = info.get("likesCount")
                    bookInfo.pages = info.get("pagesCount")
                    bookInfo.title = Converter('zh-hans').convert(info.get("title", "")).replace("'", "\"")
                    bookInfo.epsCount = info.get("epsCount")
                    bookInfo.tags = info.get("tags", [])
                    if bookInfo.tags:
                        bookInfo.tags = Converter('zh-hans').convert(",".join(bookInfo.tags))
                    bookInfo.categories = info.get("categories", [])
                    if bookInfo.categories:
                        bookInfo.categories = Converter('zh-hans').convert(",".join(bookInfo.categories))
                    bookInfo.path = info.get("thumb", {}).get("path", "")
                    bookInfo.fileServer = info.get("thumb", {}).get("fileServer", "")
                    bookInfo.originalName = info.get("thumb", {}).get("originalName", "").replace("'", "\"")
                    bookInfo.totalLikes = info.get("totalLikes")
                    bookInfo.totalViews = info.get("totalViews")
                    self._updateIds[bookInfo.id] = bookInfo
                    self._resultQueue.put(bookInfo.id)

        except Exception as es:
            Log.Error(es)

    def Run(self):
        page = 1
        maxPage = 1
        categoryIndex = 1
        while categoryIndex < len(self.idToCateGoryBase):
            categoryIndex, page, maxPage = self.LoadNextPage2(categoryIndex, page, maxPage)

        Log.Info("star update book, len:{}".format(len(self._needUpIds)))
        for bookId in self._needUpIds:
            task = Server().Send(req.GetComicsBookReq(bookId), isASync=False)
            if hasattr(task.res, "raw"):
                self.OpenBookBack(task.res.raw.text)
        self._resultQueue.put(0)
        return

    # def Run2(self):
    #     count = 10000
    #     while count >= 0:
    #         count -= 1
    #         self.LoadRandomNextPage()
    #         time.sleep(1)

    def Main(self):
        while True:
            try:
                task = self._resultQueue.get(True)
            except Exception as es:
                continue
                pass
            self._resultQueue.task_done()
            try:
                if not self.RunMain(task):
                    break
            except Exception as es:
                Log.Error(es)
        pass
        return

    def RunMain(self, task):
        bookId = task
        if bookId == 0:
            Log.Info("end, exit")
            return False

        book = self._updateIds.get(bookId)
        assert isinstance(book, DbBook)
        if bookId in self.books:
            oldBooks = self.books.get(bookId)
            if book.updated_at == oldBooks.updated_at:
                return True
            else:
                oldBooks.updated_at = book.updated_at
                oldBooks.path = book.path
                oldBooks.finished = book.finished
                oldBooks.categories = book.categories
                oldBooks.author = book.author
                oldBooks.chineseTeam = book.chineseTeam
                oldBooks.title = book.title
                oldBooks.description = book.description
                oldBooks.tags = book.tags
                oldBooks.fileServer = book.fileServer
                oldBooks.originalName = book.originalName
                oldBooks.epsCount = book.epsCount
                oldBooks.pages = book.pages
                oldBooks.likesCount = book.likesCount
                oldBooks.totalViews = book.totalViews
                oldBooks.totalLikes = book.totalLikes
            print("update BookId {}".format(bookId))
        else:
            if not self.BaiduFanyi(bookId):
                return True
            self.books[bookId] = book
            oldBooks = book
            print("add new BookId {}".format(bookId))
        self.count += 1
        self._updateIds.pop(bookId)
        self.AddHistory(oldBooks)
        # print("count "+str(self.count)+"/"+str(len(self.books)))
        # if self.count % 100 == 0:
        self.cur.execute("COMMIT")
        return True

    def BaiduFanyi(self, taskId):
        book = self._updateIds.get(taskId)
        salt = randint(32768, 65536)
        q = book.title
        sign = self.appid + q + str(salt) + self.secretKey
        sign = md5(sign.encode()).hexdigest()
        myurl = self.url + '?appid=' + self.appid + '&q=' + parse.quote(q) + '&from=' + self.fromLang + '&to=' + self.toLang + '&salt=' + str(
        salt) + '&sign=' + sign
        try:
            data = requests.get(myurl)
            result = json.loads(data.text)
            string = ''
            for word in result['trans_result']:
                if word == result['trans_result'][-1]:
                    string += word['dst']
                else:
                    string += word['dst'] + '\n'
            book.title2 = string
            time.sleep(0.1)
            return True
        except Exception as Ex:
            Log.Error(Ex)
            self._resultQueue.put(taskId)
            return False


if __name__ == "__main__":
    config.LogIndex = 1
    Log.Init()
    Log.UpdateLoggingLevel()
    config.HttpProxy = "http://127.0.0.1:10809"
    config.CanWaifu2x = False
    data = Server().Send(req.LoginReq("tonquer2", "tonquer2"), isASync=False)
    Server().token = data.res.data.get("token")

    data2 = Server().Send(req.CategoryReq(), isASync=False)
    a = MainInfo()

    for info in data2.res.data.get("categories", {}):
        if info.get("isWeb"):
            continue
        a.idToCateGoryBase.append(info.get("title"))
    # time.sleep(12)
    a.thread.start()
    a.Main()
    print("exit")
    pass