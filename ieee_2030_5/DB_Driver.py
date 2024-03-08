from peewee import *
from playhouse.shortcuts import model_to_dict
from datetime import date, datetime, timedelta
#import numpy as np
import pandas as pd

Readings_DB = SqliteDatabase('Readings.db')

class Reading(Model):
    device = CharField(default="Unknown")
    timestamp = DateTimeField(primary_key=True)
    pv1_mode = IntegerField(default=0)
    pv1_vol = FloatField(default=0.0)
    pv1_cur = FloatField(default=0.0)
    pv2_mode = IntegerField(default=0)
    pv2_vol = FloatField(default=0.0)
    pv2_cur = FloatField(default=0.0)
    pv3_mode = IntegerField(default=0)
    pv3_vol = FloatField(default=0.0)
    pv3_cur = FloatField(default=0.0)
    pv4_mode = IntegerField(default=0)
    pv4_vol = FloatField(default=0.0)
    pv4_cur = FloatField(default=0.0)
    link_vol = FloatField(default=0.0)
    pv1_temp = FloatField(default=0.0)
    pv2_temp = FloatField(default=0.0)
    inv_temp = FloatField(default=0.0)
    grid_mode = IntegerField(default=0)
    grid_vol = FloatField(default=0.0)
    grid_cur = FloatField(default=0.0)
    grid_freq = FloatField(default=0.0)
    real_pow = FloatField(default=0.0)
    react_pow = FloatField(default=0.0)
    appr_pow = FloatField(default=0.0)
    pow_factor = FloatField(default=0.0)
    class Meta:
        database = Readings_DB # This model uses the "people.db" database.

def LoadReadingsDB (conn_only=False):
    Readings_DB.connect(reuse_if_open=True)
    if conn_only == False:
        tables = Readings_DB.get_tables()
        if Reading not in tables:
            Readings_DB.create_tables([Reading])
        print (f"Total Readings Count : {len(Reading.select())}")
        for reading in Reading.select().dicts()[-20:]:
            print(reading)

def CloseReadingsDB ():
    Readings_DB.close()

def NewReading (device, timestamp):
    return Reading (device=device, timestamp=timestamp)

def SaveReading (reading):
    print (reading.save(force_insert=True))

if __name__ == '__main__':
    LoadReadingsDB ()
    if 0:
        reading = Reading(device='dev_XX', timestamp=datetime.now())
        print (reading.save(force_insert=True))

    device = 'dev_2'
    date = date.today()
    date_next = date+timedelta(days=+1)
    date_str = date.strftime('%Y-%m-%d')
    date_next_str = date_next.strftime('%Y-%m-%d')
    reading = Reading.select().where((Reading.device == device)
                                    & (Reading.timestamp.between(date, date_next)))
    df = pd.DataFrame(list(reading.dicts()))
    df.set_index('timestamp', inplace=True)
    print(df.tail(1))

    day_df = pd.DataFrame([model_to_dict(Reading())]*48)
    day_df['timestamp'] = pd.date_range(date_str, periods=48, freq='30T')
    day_df.set_index('timestamp', inplace=True)
    df = df.resample('30T').mean()
    day_df.update(df)
    print(day_df)


    # device list
    devices = Reading.select(Reading.device).distinct()
    print (f"Num of Devices : {len(devices)}")
    for reading in devices:
        print('\t- ', reading.device)

    df = pd.DataFrame(list(Reading.select().dicts()))
    print (df.tail(20))
    Readings_DB.close()
'''
tables = db.get_tables()
if Person not in tables:
    db.create_tables([Person])
if Pet not in tables:
    db.create_tables([Pet])

if 0:
    Pet.delete().execute()

if 0:
    #uncle_bob = Person(name='Bob', birthday=date(1960, 1, 15))
    #uncle_bob.save()  # bob is now stored in the database
    herb = Person(name='Herb', birthday=date(1944, 1, 15))
    herb.save() # bob is now stored in the database

for person in Person.select():
    print(person.name, person.birthday)
for pet in Pet.select():
    print(pet.name, pet.animal_type)

if 0:
    uncle_bob = Person.get(Person.name == 'Bob')
    herb = Person.get(Person.name == 'Herb')
    bob_kitty = Pet.create(owner=uncle_bob, name='Kitty', animal_type='cat')
    herb_fido = Pet.create(owner=herb, name='Fido', animal_type='dog')
    herb_mittens = Pet.create(owner=herb, name='Mittens', animal_type='cat')
    herb_mittens_jr = Pet.create(owner=herb, name='Mittens Jr', animal_type='cat')
    #Pet.insert_many([bob_kitty, herb_fido, herb_mittens, herb_mittens_jr])
    for pet in Pet.select():
        print(pet.name, pet.animal_type)
'''