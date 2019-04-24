import os
from sys import exit, exc_info, argv
from multiprocessing import Pool, current_process
import random
import json
import requests
import numpy as np
import pandas as pd
import datetime


class ChallengeEnvironment():
    def __init__(self, experimentCount=256, userID="KDDChallengeUser",
                 baseuri="https://nlmodelflask.eu-gb.mybluemix.net", locationId="abcd123", resolution="test", timeout=0,
                 realworkercount=1):

        self._resolution = resolution
        self._timeout = timeout
        self._realworkercount = realworkercount

        self.policyDimension = 2
        self._baseuri = baseuri
        self._locationId = locationId
        self.userId = userID
        self._experimentCount = experimentCount
        self.experimentsRemaining = experimentCount

    def reset(self):
        self.experimentsRemaining = self._experimentCount

    def simplePostAction(self, action):
        cached = False
        actionUrl = '%s/api/action/v0/create' % self._baseuri
        ITN_a = str(action[0]);
        IRS_a = str(action[1]);
        try:
            ITN_time = "%d" % (action[2]);
        except:
            ITN_time = None;
        try:
            IRS_time = "%d" % (action[3]);
        except:
            IRS_time = None;
        seed = random.randint(0, 100)
        envID = "none"

        itnClause = {"modelName": "ITN", "coverage": ITN_a} if ITN_time is None else {"modelName": "ITN",
                                                                                      "coverage": ITN_a,
                                                                                      "time": "%s" % ITN_time}
        irsClause = {"modelName": "IRS", "coverage": IRS_a} if IRS_time is None else {"modelName": "IRS",
                                                                                      "coverage": IRS_a,
                                                                                      "time": "%s" % IRS_time}

        actions = json.dumps({"actions": [itnClause, irsClause],
                              "environmentId": envID, "actionSeed": seed});
        try:
            reward = self.get_cache(float(ITN_a), float(IRS_a), int(ITN_time), int(IRS_time), envID, int(seed))
            if reward is not None:
                cached = True
            else:
                response = requests.post(actionUrl, data=actions,
                                         headers={'Content-Type': 'application/json', 'Accept': 'application/json'});
                data = response.json()
                reward = -float(data['data'])
        except Exception as e:
            print(e);
            reward = float('nan')
        return [reward, datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), float(ITN_a), float(IRS_a), int(ITN_time), int(IRS_time), envID, int(seed), cached]

    def evaluateReward(self, data, coverage=1):
        from numpy import ndarray
        # print(self.experimentsRemaining, " exps left")
        if self.experimentsRemaining <= 0:
            raise ValueError('You have exceeded the permitted number of experiments')
        if type(data) is not ndarray:
            raise ValueError('argument should be a numpy array')

        from multiprocessing import Pool
        if len(data.shape) == 2:  # array of policies
            # self.experimentsRemaining -= data.shape[0]
            pool = Pool(self._realworkercount)
            result = pool.map(self.simplePostAction, data)
            pool.close()
            pool.join()
        else:
            result = self.simplePostAction(data)
            # self.experimentsRemaining -= 1
        result = np.array(result)
        self.save_cache(result)
        return result

    def save_cache(self, result):
        if len(result.shape) != 2:
            result = np.array([result])
        new_cache = pd.DataFrame(result, columns=['reward', 'time', 'ITN_a', 'IRS_a', 'ITN_time', 'IRS_time', 'envID', 'seed', 'cached'])
        new_cache = new_cache.loc[~new_cache.cached, new_cache.columns != 'cached']
        with open('cache/cache.csv', 'a') as f:
            new_cache.to_csv(f, header=False)

    def get_cache(self, ITN_a, IRS_a, ITN_time, IRS_time, envID, seed):
        reward = self.cache[(self.cache.ITN_a == ITN_a) & (self.cache.IRS_a == IRS_a) & (self.cache.ITN_time == ITN_time)
                   & (self.cache.IRS_time == IRS_time) & (self.cache.envID == envID) & (self.cache.seed == seed)]
        if len(reward) == 0:
            reward = None
        else:
            reward = reward.sort_values('time', ascending=False)['reward'][0]
        return reward