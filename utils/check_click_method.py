from django.shortcuts import redirect

def into_method(*args, **kwargs):
    """
    判断是点击跳转还是手动输入url
    :return:
    """
    request = args[0]
    try:
        http_referer = request.META['HTTP_REFERER']
        return True
    except Exception as e:
        return False


def check_click_method(func):
    def inner(*args, **kwargs):
        if not into_method(*args, **kwargs):
            return redirect('/gateway/index')
        return func(*args, **kwargs)
    return inner








