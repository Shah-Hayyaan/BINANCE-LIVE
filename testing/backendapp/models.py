from django.db import models

class HistoryData(models.Model):
    symbol = models.CharField(max_length=20)  
    timestamp = models.DateTimeField(primary_key=True)          
    open_price = models.DecimalField(max_digits=10, decimal_places=2)
    high_price = models.DecimalField(max_digits=10, decimal_places=2)
    low_price = models.DecimalField(max_digits=10, decimal_places=2)
    close_price = models.DecimalField(max_digits=10, decimal_places=2)
    volume = models.BigIntegerField()

    class Meta:
        db_table = 'HistoryData'
        constraints = [
            models.UniqueConstraint(
                fields=['symbol', 'timestamp'],
                name='unique_historydata_symbol_timestamp'
            )
        ]

class Binance_Data(models.Model):
    symbol = models.CharField(max_length=20)  
    timestamp = models.DateTimeField(primary_key=True)          
    open_price = models.DecimalField(max_digits=10, decimal_places=2)
    high_price = models.DecimalField(max_digits=10, decimal_places=2)
    low_price = models.DecimalField(max_digits=10, decimal_places=2)
    close_price = models.DecimalField(max_digits=10, decimal_places=2)
    volume = models.DecimalField(max_digits=30, decimal_places=2)

    class Meta:
        db_table = 'binancedata'
        constraints = [
            models.UniqueConstraint(
                fields=['symbol', 'timestamp'],
                name='unique_Binance_Data_symbol_timestamp'
            )
        ]
        
class IbApi_Data(models.Model):
    symbol = models.CharField(max_length=20)  
    timestamp = models.DateTimeField(primary_key=True)          
    open_price = models.DecimalField(max_digits=10, decimal_places=2)
    high_price = models.DecimalField(max_digits=10, decimal_places=2)
    low_price = models.DecimalField(max_digits=10, decimal_places=2)
    close_price = models.DecimalField(max_digits=10, decimal_places=2)
    volume = models.DecimalField(max_digits=30, decimal_places=2)

    class Meta:
        db_table = 'IbApi_Data'
        constraints = [
            models.UniqueConstraint(
                fields=['symbol', 'timestamp'],
                name='unique_IbApi_Data_symbol_timestamp'
            )
        ]