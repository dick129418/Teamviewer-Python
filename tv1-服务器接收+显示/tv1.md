# 用Python 写一个Teamviewer

## 起因

最近teamviewer老是怀疑商用,卸载重装/删除注册表/改mac地址无效,加上最近突然又研究回到tornado-socket,于是看看能不能自己写个teamviewer.这也是因为在之前有接触过pywin32做过模拟按键,不然也肯定不会有这个想法

tornado-socket参考来自[王桂杰](https://github.com/gjwang/towsclient)大兄弟的例子

## 放在前面

[最终效果](http://118.24.53.19:9000/static/upload/3497b5b6-572c-11e8-b3b4-0242ac110002.gif)

就不放图了,想看看就点开,1M 腾讯云..

这是本机被控+本机server, 想要真正远程,也就把server跟被控放在两台电脑上面就行了.

## 构思

远程,最简单的思路就是截屏然后传输,但是这样传输数据会很大.然后就想到了两次截屏,然后对比出两次屏幕不同处,然后进行传输.

于是百度了下`PIL`对比两张图片.发现了`PIL.ImageGrab`和`PIL.ImageChops`,例子如下:

    im1 = ImageGrab.grab() //截图
    im2 = ImageGrab.grab() //截图
    diff = ImageChops.difference(im1, im2)
    box = diff.getbbox() //找出不同区域
    img = im2.crop(box) //抠图

图片扣出来了, 区域找到,那么就只剩发送数据了,不过在发送之前考虑到以后可能还会发送同类型其他数据,于是给数据加了个标签**screen**, 一个就三个数据 screen, box, 图片的二进制

为了避免交互的麻烦, 我把这三个数据组合成了一个二进制字符串, 大概长这样

    b'screen<------>(x1, y1, x2, y2)<------>这里是图片的二进制数据'
    <------> 这里是为了另一端获取到数据进行 split(b'<------>')转换成原始数据

然后调用王兄弟的方法, send(data, is_bin=True), server接收到之后, 转发给控制端,由控制端解析数据

## 设计

由于想要急切地看到项目可行性,于是我直接将显示输出在了server端.

大概就是:

    [被控制端] -> [server
                    -> 开一个线程进行显示]

本来的样子:

    [被控制端] -> [server] -> [控制端]

毕竟,要是做不出来,早点放弃也是明智的~

界面采用PYQT5, 界面块儿代码说明:

    def show(label):
        last_img = None
        sleep(3) // 这里如果不睡眠,好像导致线程里面的东西跑在前面会有问题
        w_width, w_height = None, None //界面进行缩放的时候 方便我们跟着缩放图片
        while 1:
            box, img = q.get() //获取数据
            box = eval(box.decode())

            // 下面会有很多坑, 还是对这块儿不熟悉

            // 为了优化速率,我们直接将二进制数据加载进内存.这就比把数据写入文件,再从文件读取快多了
            img_io = BytesIO(img) 
            img = Image.open(img_io)
            if last_img:
                if not box: continue
                // 因为我们只是抠图,所以我们要把后面的图片根据区域给它覆盖上去
                last_img.paste(img, box)
            else:    // 第一次接收到数据.
                // 测试的时候很重要!!!!
                // 因为只想快点看效果, 所以没做流程控制,可能出现的问题就是,如果先启动被控制端, 那么最初的截屏就被传输给丢失了,所以测试请先启动server,保证能收到第一张全屏图.
                last_img = img
            
            // 下面两句是坑之二
            imgqt = ImageQt.ImageQt(last_img)
            qimg = QtGui.QImage(imgqt)
            pix = QtGui.QPixmap(qimg)
            
            width, height = int(w.width()), int(w.height())
            if (w_width, w_height) != (width, height):
                w_width, w_height = width, height
                l1.setFixedHeight(w_height)
                l1.setFixedWidth(w_width)
            pix = pix.scaled(w_width, w_height)
            label.setPixmap(pix)

    l1 = QtWidgets.QLabel(w)
    l1.move(x, y)
    l1.show()
    threading._start_new_thread(show, (l1,))

## 踩坑

所谓的踩坑就是在这上面画了很长时间而已,除了百度,Google也没啥了

1.最初的单纯想要看到效果,就是采用的写入图片,可是图片数据传输过来在写入数据的时候,打开说图片数据错误. 原来在传输的时候需要将PIL.Image类型转为io.BytesIO类型进行传输

2.图片数据在接收到的时候需要用PIL.ImageQt加载,然后用QtGui.QImage加载PIL.ImageQt类型的数据.最重还要转为QtGui.QPixmap.**然而并不能知其所以然..**

**想要测试的小伙伴注意**: 先启动server,再启动被控制端,原因在上面的代码块中有解释. 这里再说一次,避免有些人不喜欢看代码跳过了.
