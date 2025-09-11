import wx

def callback(a: int, b: int):
    """ """
    print(f"a={a}, id(a)={id(a)}")
    print(f"b={b}, id(b)={id(b)}")


def main():
    app = wx.AppConsole()

    b = 1
    c = 2
    wx.CallLater(1000, callback, b, c)
    b += 1
    c += 1
    wx.CallLater(2000, callback, b, c)
    b += 1
    c += 1
    wx.CallLater(3000, callback, b, c)

    app.MainLoop()


if __name__ == "__main__":
    main()
