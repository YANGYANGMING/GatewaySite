from gateway import models


class Delete_data():

    def count_gwdata(self):
        """删除超限网关数据"""
        db_count = models.GWData.objects.all().count()
        if db_count > 512:
            diffience_count = db_count - 512
            obj_list = list(models.GWData.objects.all()[:int(diffience_count)])
            for i in obj_list:
                i.delete()

    # def count_postdata(self):
    #     """删除超限返回数据"""
    #     db_count = models.Post_Return.objects.all().count()
    #     if db_count > 512:
    #         diffience_count = db_count - 512
    #         obj_list = list(models.GWData.objects.all()[:int(diffience_count)])
    #         for i in obj_list:
    #             i.delete()