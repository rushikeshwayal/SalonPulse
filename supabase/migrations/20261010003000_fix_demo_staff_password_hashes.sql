-- Repair temporary demo login hashes so the documented passwords validate.
-- Users are forced to choose a new password on their first successful sign-in.
update public.staff_users set
  password_hash = 'pbkdf2_sha256$420000$23iYiCHmItKShez99fmXmWPU$5OIytF91x0M09r_5_-HPzAaFUpr53TIDCoJZ4auk8W0',
  must_change_password = true, updated_at = timezone('utc', now())
where username = 'owner' and email = 'owner@salonpulse.demo';

update public.staff_users set
  password_hash = 'pbkdf2_sha256$420000$Qaxp9eRhlRvi95K0pwEIOerl$6dtYYrJLsRMuyckc0QrZUw2uVbDNHXiYQgZIodmylDw',
  must_change_password = true, updated_at = timezone('utc', now())
where username = 'aarav' and email = 'aarav.patil@salonpulse.demo';

update public.staff_users set
  password_hash = 'pbkdf2_sha256$420000$4CGHxqs1t5TvPNezMXpOxWrV$otoUciAgH-RfsFidVrHA6yl4U7VwekLUxfAfTsYYSCU',
  must_change_password = true, updated_at = timezone('utc', now())
where username = 'rohan' and email = 'rohan.jadhav@salonpulse.demo';

update public.staff_users set
  password_hash = 'pbkdf2_sha256$420000$s-1scbpsXi1XGG97_YYf8iOw$TbVmDvb1Jv6ecXjqiauQHhP51w8axIB-JP9X7w2ToII',
  must_change_password = true, updated_at = timezone('utc', now())
where username = 'kabir' and email = 'kabir.shah@salonpulse.demo';

update public.staff_users set
  password_hash = 'pbkdf2_sha256$420000$sU6ogeeSBNbNNuBcv1k4ncb7$SzGgO-3Iyq0BG_ao6Y8DZV5BUDOUyamWlWDjZlkoUbs',
  must_change_password = true, updated_at = timezone('utc', now())
where username = 'dev' and email = 'dev.kulkarni@salonpulse.demo';

update public.staff_users set
  password_hash = 'pbkdf2_sha256$420000$CtK1t4WZEPW3-WIIudz8sZjZ$9qwhrAFtPRqzAzcgtSLLCnf2tjvtZJmfx0_3E3IiXNM',
  must_change_password = true, updated_at = timezone('utc', now())
where username = 'ishaan' and email = 'ishaan.more@salonpulse.demo';

update public.staff_users set
  password_hash = 'pbkdf2_sha256$420000$M1u_l-lwKUC3Nnc5wn7o4G-s$ibaVw8SeZKJVk51D7h8vXmC33IfJTplRKTpLRK5Mx9c',
  must_change_password = true, updated_at = timezone('utc', now())
where username = 'arjun' and email = 'arjun.deshmukh@salonpulse.demo';
