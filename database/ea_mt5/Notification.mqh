#ifndef TFM_NOTIFICATION_MQH
#define TFM_NOTIFICATION_MQH

void TFM_SendNotification(string msg, bool allowPush=true)
{
   if(PrintToExperts)
      Print(msg);

   if(allowPush && EnablePushNotification)
      SendNotification(msg);
}

void TFM_SaveLastNotifiedStates(string eventKey, string snapshot)
{
   TFM_LastNotifiedH1State  = TFM_H1State;
   TFM_LastNotifiedM15State = TFM_M15State;
   TFM_LastNotifiedM5State  = TFM_M5State;

   TFM_LastEventKey = eventKey;
   TFM_LastSnapshot = snapshot;
   TFM_HasSnapshot  = true;
}

void TFM_ProcessNotification()
{
   string eventKey = TFM_BuildEventKey();

   if(eventKey == "")
      return;

   if(!TFM_HasSnapshot)
   {
      TFM_H1NewMarker  = (TFM_H1State.direction != TFM_DIR_NONE && TFM_H1State.time > 0);
      TFM_M15NewMarker = (TFM_M15State.direction != TFM_DIR_NONE && TFM_M15State.time > 0);
      TFM_M5NewMarker  = (TFM_M5State.direction != TFM_DIR_NONE && TFM_M5State.time > 0);

      string firstSnapshot = TFM_BuildSnapshot();
      TFM_SaveLastNotifiedStates(eventKey, firstSnapshot);

      if(NotifyOnFirstLoad)
         TFM_SendNotification(firstSnapshot, PushOnFirstLoad);

      return;
   }

   // Jangan kirim notif hanya karena umur candle bertambah.
   // Notif hanya dikirim jika ada perubahan direction/source/time pada H1/M15/M5.
   if(eventKey == TFM_LastEventKey)
      return;

   TFM_H1NewMarker  = !TFM_StateEquals(TFM_H1State, TFM_LastNotifiedH1State);
   TFM_M15NewMarker = !TFM_StateEquals(TFM_M15State, TFM_LastNotifiedM15State);
   TFM_M5NewMarker  = !TFM_StateEquals(TFM_M5State, TFM_LastNotifiedM5State);

   string snapshot = TFM_BuildSnapshot();

   if(snapshot == "")
      return;

   TFM_SaveLastNotifiedStates(eventKey, snapshot);
   TFM_SendNotification(snapshot, true);
}

#endif