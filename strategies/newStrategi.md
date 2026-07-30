analisa path strategi ini : 
C:\codingVibes\mt5\engulfing\strategies

intruksi : 
- saya mau menambahkan strategi tanpa filter di dalam nya 
- jadi konsep strategi ini adalah bot akan selalu jalan atau running execute market secara terus menerus mengikuti pergerakan real-time harga saat itu juga 
- jadi konsep ny ini tidak menggunkan OP execute langsung tapi menggunakan execute OP dengan BUY/SELL STOP 
- nah untuk awal mesin ini d jlaankan akan langsung meng execute market, dengan awalan HARUS BUY market untu OP nya, dan jika BUY maka lawannya adalah pasang sekalian dengan OP ke-2 yaitu SELL stop dengan jarak 100 pts point, jarak dari OP 1 nya, dan sebalik ny jika itu berawalan SELL maka langsung pasang BUY STOP nya dengan jarak 100 pts juga 
- nah d sini yg pasti aalah OP 1 pasti jalan pertama, maka akan d pasang juga bebrbarengan denagn op 1 op2 ny juga d pasang secara berbbarengan, OP 1 itu execute langsung BUY dan op 2 itu SELL stop, nah untu OP 1 nya itu jadikan inputan untuk strategi ini d .env 
- nah untu OP2 ini saya OP 2 ini akan bergerak secara dinamis mengikuti pergerakan Market harga running realtime nya, misa dengan contoh,jika awal OP 1 adalah BUY amak op 2 adalah SELL stop dan market sedang bergerak ke atas denan asumsi profit +, dan secara dinamis OP 2 SELL stop ini akan bergerak dinamis seolah olah mengejar Harga market yg running ny dengan jarak 50 pts jarak pergerakan kelipatan setiap market bergerak menjauh dari OP 2 ini, jadi perkelipatan 50 pts op 2 akan mengikuti harga market running real-time nya 
- dan untuk akan berlansung terus meneru mengikuti harga market bergerak untuk OP2 ny itu, nah misal OP ini adalah SELL stop dan sedang mengikuti pergerakan mendekat ke market running, misal OP 2 ini tersentuh maka secara otomatis OP 1 itu akan ter close otomatis dengan asumsi profit + y kan, dan untuk OP 2 d sini akan menjadi OP 1 karna execute terbuka, jadi intinya OP 1 itu adalah execute terbuka setiap kali OP 2 terbukan akan menjadi OP 1 dan secara otomatis bersamaan dengan terbuka nya OP 2 yg berubah menjadi OP1 d situ masuk lagi OP 2 BUY STOP dengan OP 2 dan menjadi op 1 itu sebelumny adalah OP 2 SELL Stop gitu, dan begitu seterus nya 

- dan intinya, ketika awal running sistem, sistem akan OP langsung dengan lot yg d sediakan d .env dan execute BUY intpuan d .env, dan secara otomatis sstem akan memasang 2 OP, OP 1 adaah execute awal, dan OP 2 adalah kebalikanya yaitu SELL stOp. 
- setiap kali OP 2 tersentuh ada 3 kejadian terjadi yaitu : 
  1. OP 2 SELL stop akan berubah menjadi OP 1 yg running, 
  2. ke dua mengclose OP 1 yg sebelum ny (Posisi BUy)
  3. pasang OP 2 berikutnya yg dinamis (yaitu BUY STOP) 

jika adan paham dengan strategi ini berikan nama untuk strategi ini dan buatkan folder nya d sini : C:\codingVibes\mt5\engulfing\strategies bersebelahan dengan strategi d engulfing 
serja buatkan inputan terpisah untuk strategi d ini d .env untuk config yg d perlukanya, serta buatkan planning nya dulu, dan diskusikan dengan saya 