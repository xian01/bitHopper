#!/usr/bin/python
#License#
#bitHopper by Colin Rice is licensed under a Creative Commons Attribution-NonCommercial-ShareAlike 3.0 Unported License.
#Based on a work at github.com.

import os.path
import time

from twisted.web import server, resource

class Scheduler(object):
   def __init__(self,bitHopper):
      self.bh = bitHopper
      self.initData()
   @classmethod
   def initData(self,):
      #self.bh.log_msg("<Scheduler> initData")
      return

   @classmethod
   def server_update(self,):
      return

   @classmethod
   def select_best_server(self,):
      return

   @classmethod
   def select_friendly_server(self):
      return

   @classmethod
   def select_backup_server(self,):
      return


class DefaultScheduler(Scheduler):
   def __init__(self,bitHopper):
      self.bh = bitHopper
      self.difficultyThreshold = 0.435
      self.initData()
      
   def initData(self,):
      if self.bh.options.threshold:
         #self.bh.log_msg("Override difficulty threshold to: " + str(self.bh.options.threshold), cat='scheduler-default')
         self.difficultyThreshold = self.bh.options.threshold

   def select_best_server(self,):
      #self.bh.log_dbg('select_best_server', cat='scheduler-default')
      server_name = None
      difficulty = self.bh.difficulty.get_difficulty()
      nmc_difficulty = self.bh.difficulty.get_nmc_difficulty()
      min_shares = difficulty * self.difficultyThreshold
        
      #self.bh.log_dbg('min-shares: ' + str(min_shares), cat='scheduler-default')  
      for server in self.bh.pool.get_servers():
         info = self.bh.pool.get_entry(server)
         if info['api_lag'] or info['lag']:
            continue
         if info['role'] not in ['mine','mine_nmc','mine_slush','mine_friendly']:
            continue
         if info['role'] in ['mine', 'mine_friendly']:
            shares = info['shares']
         elif info['role'] == 'mine_slush':
            shares = info['shares'] * 4
         elif info['role'] == 'mine_nmc':
            shares = info['shares']*difficulty / nmc_difficulty
         else:
            shares = 100* info['shares']
         if shares< min_shares:
            min_shares = shares
            #self.bh.log_dbg('Selecting pool ' + str(server) + ' with shares ' + str(info['shares']), cat='scheduler-default')
            server_name = server
         
      if server_name == None:
         server_name = self.select_friendly_server()

      if server_name == None: return self.select_backup_server()
      else: return server_name   
   
   def select_friendly_server(self):
      server_name = None
      most_shares = self.bh.difficulty.get_difficulty() * 2
      for server in self.bh.pool.get_servers():
         info = self.bh.pool.get_entry(server)
         if info['role'] != 'mine_friendly':
            continue
         if info['shares'] > most_shares and info['lag'] == False:
            server_name = server
            most_shares = info['shares']
            self.bh.log_dbg('select_friendly_server: ' + str(server), cat='scheduler-default')
      
      return server_name
   
   def select_latehop_server(self):
      server_name = None
      max_share_count = 1
      for server in self.bh.pool.get_servers():
         info = self.bh.pool.get_entry(server)
         if info['api_lag'] or info['lag']:
            continue
         if info['role'] != 'backup_latehop':
            continue
         if info['shares'] > max_share_count:
            server_name = server
            max_share_count = info['shares']
            self.bh.log_dbg('select_latehop_server: ' + str(server), cat='scheduler-default')

      return server_name   

   def select_backup_server(self,):
      #self.bh.log_dbg('select_backup_server', cat='scheduler-default')
      server_name = None
      reject_rate = 1

      server_name = self.select_latehop_server()

      if server_name == None:
         for server in self.bh.pool.get_servers():
            info = self.bh.pool.get_entry(server)
            if info['role'] not in ['backup', 'backup_latehop']:
               continue
            if info['api_lag'] or info['lag']:
               continue
            rr_server = float(info['rejects'])/(info['user_shares']+1)
            if rr_server < reject_rate:
               server_name = server
               self.bh.log_dbg('select_backup_server: ' + str(server), cat='scheduler-default')
               reject_rate = rr_server

      if server_name == None:
         #self.bh.log_dbg('Try another backup' + str(server), cat='scheduler-default')
         min_shares = 10**10
         for server in self.bh.pool.get_servers():
            info = self.bh.pool.get_entry(server)
            if info['api_lag'] or info['lag']:
                continue
            if info['role'] not in ['mine','mine_nmc','mine_slush']:
                continue
            if info['role'] == 'mine':
                shares = info['shares']
            elif info['role'] == 'mine_slush':
                shares = info['shares'] * 4
            elif info['role'] == 'mine_nmc':
                shares = info['shares']*difficulty / nmc_difficulty
            else:
                shares = info['shares']
            if shares < min_shares and info['lag'] == False:
                min_shares = shares
                #self.bh.log_dbg('Selecting pool ' + str(server) + ' with shares ' + str(shares), cat='scheduler-default')
                server_name = server
      
      if server_name == None:
         #self.bh.log_dbg('Try another backup pt2' + str(server), cat='scheduler-default')
         for server in self.bh.pool.get_servers():
            info = self.bh.pool.get_entry(server)
            if info['role'] != 'backup':
               continue
            server_name = server
            break

      return server_name


   def server_update(self,):
      #self.bh.log_dbg('server_update', cat='scheduler-default')
      valid_roles = ['mine', 'mine_slush','mine_nmc']
      current_pool = self.bh.pool.get_entry(self.bh.pool.get_current())
      if current_pool['role'] not in valid_roles:
         return True
    
      if current_pool['api_lag'] or current_pool['lag']:
         return True

      current_role = current_pool['role']
      if current_role == 'mine' or current_role == 'mine_friendly':
         difficulty = self.bh.difficulty.get_difficulty()
      if current_role == 'mine_nmc':
         difficulty = self.bh.difficulty.get_nmc_difficulty()
      if current_role == 'mine_slush':
         difficulty = self.bh.difficulty.get_difficulty() * .25
      if current_pool['shares'] > (difficulty * self.difficultyThreshold):
         return True

      min_shares = 10**10

      for server in self.bh.pool.get_servers():
         pool = self.bh.pool.get_entry(server)
         if pool['shares'] < min_shares:
            min_shares = pool['shares']

      if min_shares < current_pool['shares']*.90:
        return True       

      return False

class RoundTimeScheduler(Scheduler):
   def select_best_server(self,):
      return
   def select_backup_server(self,):
      return


class RoundTimeDynamicPenaltyScheduler(Scheduler):
   def select_best_server(self,):
      return
   def select_backup_server(self,):
      return


class SliceScheduler(Scheduler):
   def __init__(self,bitHopper):
      self.bh = bitHopper
      self.bitHopper = self.bh
      self.difficultyThreshold = 0.435
      self.sliceinfo = {}
      self.initData()
      self.lastcalled = time.time()
      self.index_html = 'index-slice.html'
      
   def initData(self,):
        if self.bh.options.threshold:
         #self.bh.log_msg("Override difficulty threshold to: " + str(self.bh.options.threshold), cat='scheduler-default')
         self.difficultyThreshold = self.bh.options.threshold
        for server in self.bh.pool.get_servers():
            self.sliceinfo[server] = -1

   def select_best_server(self,):
      #self.bh.log_dbg('select_best_server', cat='scheduler-default')
      server_name = None
      difficulty = self.bh.difficulty.get_difficulty()
      nmc_difficulty = self.bh.difficulty.get_nmc_difficulty()
      min_shares = difficulty * self.difficultyThreshold

      valid_servers = []
      for server in self.bh.pool.get_servers():
         info = self.bh.pool.get_entry(server)
         if info['api_lag'] or info['lag']:
            continue
         if info['role'] not in ['mine','mine_nmc','mine_slush']:
            continue
         if info['role'] in ['mine']:
            shares = info['shares']
         elif info['role'] == 'mine_slush':
            shares = info['shares'] * 4
         elif info['role'] == 'mine_nmc':
            shares = info['shares']*difficulty / nmc_difficulty
         else:
            shares = 100* info['shares']
         if shares< min_shares:
            valid_servers.append(server)
         
      for server in valid_servers:
        if server not in self.sliceinfo:
            self.sliceinfo[server] = 0
        if self.sliceinfo[server] == -1:
            self.sliceinfo[server] = 0

      for server in self.sliceinfo:
        if server not in valid_servers:
            self.sliceinfo[server] = -1

      if valid_servers == []: return self.select_backup_server()
      
      min_slice = self.sliceinfo[valid_servers[0]]
      server = valid_servers[0]
      for server in valid_servers:
        if self.sliceinfo[server] < min_slice:
            min_slice = self.sliceinfo[server]
            server = valid_servers

      return server

   def select_backup_server(self,):
      #self.bh.log_dbg('select_backup_server', cat='scheduler-default')
      server_name = None
      reject_rate = 1

      if server_name == None:
         for server in self.bh.pool.get_servers():
            info = self.bh.pool.get_entry(server)
            if info['role'] not in ['backup', 'backup_latehop']:
               continue
            if info['api_lag'] or info['lag']:
               continue
            rr_server = float(info['rejects'])/(info['user_shares']+1)
            if rr_server < reject_rate:
               server_name = server
               self.bh.log_dbg('select_backup_server: ' + str(server), cat='scheduler-default')
               reject_rate = rr_server

      if server_name == None:
         #self.bh.log_dbg('Try another backup' + str(server), cat='scheduler-default')
         min_shares = 10**10
         for server in self.bh.pool.get_servers():
            info = self.bh.pool.get_entry(server)
            if info['api_lag'] or info['lag']:
                continue
            if info['role'] not in ['mine','mine_nmc','mine_slush']:
                continue
            if info['role'] == 'mine':
                shares = info['shares']
            elif info['role'] == 'mine_slush':
                shares = info['shares'] * 4
            elif info['role'] == 'mine_nmc':
                shares = info['shares']*difficulty / nmc_difficulty
            else:
                shares = info['shares']
            if shares < min_shares and info['lag'] == False:
                min_shares = shares
                #self.bh.log_dbg('Selecting pool ' + str(server) + ' with shares ' + str(shares), cat='scheduler-default')
                server_name = server
      
      if server_name == None:
         #self.bh.log_dbg('Try another backup pt2' + str(server), cat='scheduler-default')
         for server in self.bh.pool.get_servers():
            info = self.bh.pool.get_entry(server)
            if info['role'] != 'backup':
               continue
            server_name = server
            break

      return server_name


   def server_update(self,):
        #self.bitHopper.log_msg(str(self.sliceinfo))
        diff_time = time.time()-self.lastcalled
        self.lastcalled = time.time()
        current = self.sliceinfo[self.bh.pool.get_current()]
        if current == -1:
            return True

        self.sliceinfo[self.bh.pool.get_current()] += diff_time

        for server in self.sliceinfo:
            if self.sliceinfo[server] == -1:
                continue
            if current - self.sliceinfo[server] > 10:
                return True
        return False

class AltSliceScheduler(Scheduler):
   def __init__(self,bitHopper):
      self.bh = bitHopper
      self.bitHopper = self.bh
      self.difficultyThreshold = 0.435
      self.sliceinfo = {}
      self.initData()
      self.lastcalled = time.time()
      self.lastswitch = -1
      self.index_html = 'index-altslice.html'
      self.name = 'schedulter-altslice'
      self.initDone = False
      
   def initData(self,):
        if self.bh.options.threshold:
         #self.bh.log_msg("Override difficulty threshold to: " + str(self.bh.options.threshold), cat='scheduler-default')
         self.difficultyThreshold = self.bh.options.threshold
        for server in self.bh.pool.get_servers():
            info = self.bh.pool.get_entry(server)
            info['slice'] = -1
            info['slicedShares'] = 0
            info['init'] = False

   def select_best_server(self,):
      #self.bh.log_dbg('select_best_server', cat=self.name)
      server_name = None
      difficulty = self.bh.difficulty.get_difficulty()
      nmc_difficulty = self.bh.difficulty.get_nmc_difficulty()
      min_shares = difficulty * self.difficultyThreshold

      current_server = self.bh.pool.get_current()
      reslice = True
      fullinit = True
      
      for server in self.bh.pool.get_servers():
         info = self.bh.pool.get_entry(server)
         if info['slice'] > 0 or info['slicedShares'] > info['shares']:
            reslice = False
         if info['init'] == False and info['role'] in ['mine','mine_nmc','mine_slush']:
            #self.bh.log_dbg(server + " not yet initialized", cat=self.name)
            fullinit = False
      
      if self.bh.pool.get_current() == None:
         reslice = True
      elif self.bh.pool.get_entry(current_server)['lag'] == True:
         reslice = True

      if fullinit and self.initDone == False:
         self.initDone = True
         reslice = True
         
      #self.bh.log_dbg('Re-Slicing: ' + str(reslice), cat=self.name)
      if (reslice == True):
         self.bh.log_dbg('Re-Slicing...', cat=self.name)
         totalweight = 0
         for server in self.bh.pool.get_servers():
            info = self.bh.pool.get_entry(server)
            if info['role'] not in ['mine','mine_nmc','mine_slush']:
               continue
            if info['api_lag'] or info['lag']:
               continue
            if info['role'] in ['mine']:
               shares = info['shares']
            elif info['role'] == 'mine_slush':
               shares = info['shares'] * 4
            elif info['role'] == 'mine_nmc':
               shares = info['shares']*difficulty / nmc_difficulty
            else:
               shares = 100* info['shares']
               
            #self.bh.log_dbg(server + ' shares ' + str(shares))
            if shares < min_shares:
               #self.bh.log_dbg('          ' + server + ' weighted to ' + str(1 / float(shares) * difficulty), cat=self.name)
               totalweight = totalweight + (1 / float(shares) * difficulty)
               info['slicedShares'] = shares
            else:
               #self.bh.log_dbg(server + ' skipped ')
               continue
            weight = self.bh.options.altslicesize / totalweight
   
            # allocate slices         
            for server in self.bh.pool.get_servers():
               info = self.bh.pool.get_entry(server)
               if info['role'] not in ['mine','mine_nmc','mine_slush']:
                  continue
               if info['shares'] <=0: continue
               if info['role'] in ['mine']:
                  shares = info['shares']
               elif info['role'] == 'mine_slush':
                  shares = info['shares'] * 4
               elif info['role'] == 'mine_nmc':
                  shares = info['shares']*difficulty / nmc_difficulty
               else:
                  shares = 100* info['shares']
               if shares < min_shares:
                  info['slice'] = (1 / float(shares+1) * difficulty) * weight
                  self.bh.log_msg(server + " sliced to " + str(info['slice']), cat='slice')
   
      # Pick server with largest slice first
      max_slice = -1
      for server in self.bh.pool.get_servers():
         info = self.bh.pool.get_entry(server)
         if info['role'] in ['mine','mine_nmc','mine_slush'] and info['slice'] > 0 and info['lag'] == False:
            if max_slice == -1:
               max_slice = info['slice']
               server_name = server
            if info['slice'] > max_slice:
               server_name = server
               break
            
      #self.bh.log_dbg('server_name: ' + str(server_name), cat=self.name)
      if server_name == None: server_name = self.select_backup_server()
      return server_name
         

   def select_backup_server(self,):
      #self.bh.log_dbg('select_backup_server', cat='scheduler-default')
      server_name = None
      reject_rate = 1

      if server_name == None:
         for server in self.bh.pool.get_servers():
            info = self.bh.pool.get_entry(server)
            if info['role'] not in ['backup', 'backup_latehop']:
               continue
            if info['api_lag'] or info['lag']:
               continue
            rr_server = float(info['rejects'])/(info['user_shares']+1)
            if rr_server < reject_rate:
               server_name = server
               self.bh.log_dbg('select_backup_server: ' + str(server), cat='scheduler-default')
               reject_rate = rr_server

      if server_name == None:
         #self.bh.log_dbg('Try another backup' + str(server), cat='scheduler-default')
         min_shares = 10**10
         for server in self.bh.pool.get_servers():
            info = self.bh.pool.get_entry(server)
            if info['api_lag'] or info['lag']:
                continue
            if info['role'] not in ['mine','mine_nmc','mine_slush']:
                continue
            if info['role'] == 'mine':
                shares = info['shares']
            elif info['role'] == 'mine_slush':
                shares = info['shares'] * 4
            elif info['role'] == 'mine_nmc':
                shares = info['shares']*difficulty / nmc_difficulty
            else:
                shares = info['shares']
            if shares < min_shares and info['lag'] == False:
                min_shares = shares
                #self.bh.log_dbg('Selecting pool ' + str(server) + ' with shares ' + str(shares), cat='scheduler-default')
                server_name = server
      
      if server_name == None:
         #self.bh.log_dbg('Try another backup pt2' + str(server), cat='scheduler-default')
         for server in self.bh.pool.get_servers():
            info = self.bh.pool.get_entry(server)
            if info['role'] != 'backup':
               continue
            server_name = server
            break

      return server_name


   def server_update(self,):
      #self.bh.log_dbg('server_update', cat='server_update')
      diff_time = time.time()-self.lastcalled
      self.lastcalled = time.time()
      current_server = self.bh.pool.get_current()
      info = self.bh.pool.get_entry(current_server)
      info['slice'] = info['slice'] - diff_time
      #self.bh.log_dbg(current_server + ' slice ' + str(info['slice']), cat='server_update' )
      if self.initDone == False:
         self.bh.select_best_server()
         return True
      if info['slice'] <= 0:
         return True

      return False

