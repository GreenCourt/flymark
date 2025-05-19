let s:dir = expand("<sfile>:p:h:h")
let s:sep = (exists('+shellslash') && !&shellslash) ? "\\" : "/"

let g:flymark_bind = get(g:, "flymark_bind", "127.0.0.1")

aug flymark | aug END

func flymark#start() abort
  call s:server_start()

  if !s:server_is_running()
    echohl WarningMsg
    echo "failed to start server"
    echohl None
  endif

  echo "http://" .. g:flymark_bind .. ":" .. s:port

  au! flymark BufWritePost <buffer> call s:send()
  au! flymark TextChanged <buffer> call s:send()
  au! flymark InsertLeave <buffer> call s:send()
  call s:send()

  if executable("explorer.exe")
    echow system("explorer.exe http://" .. g:flymark_bind .. ":" .. s:port)
  endif
endfunc

func flymark#stop() abort
  au! flymark
  if s:server_is_running()
    call job_setoptions(s:job, #{exit_cb: {job, status -> 0}})
    call job_stop(s:job)
  endif
endfunc

func flymark#log() abort
  if !exists("s:job")
    echo "no server"
    return
  endif
  sp
  execute ch_getbufnr(s:job, "out") .. "b"
endfunc


func s:server_start() abort
  if s:server_is_running()
    return
  endif

  let s:port = get(g:, "flymark_port",
        \ system("python3 " .. shellescape(s:dir .. s:sep .. "port.py")))

  if v:shell_error
    echohl WarningMsg
    echo "port.py exited with " .. v:shell_error
    echohl None
    return
  endif

  let s:job = job_start(
        \ ["python3", "-u", s:dir .. s:sep .. "flymark.py",
        \  "--bind", g:flymark_bind,
        \  "--port", s:port,
        \ ], #{
        \   in_io : "pipe",
        \   out_io : "buffer",
        \   err_io : "out",
        \   out_modifiable: 0,
        \   exit_cb : "<SID>exit_cb",
        \ })
endfunc


func s:server_is_running()
  return exists("s:job") && job_status(s:job) == "run"
endfunc


func s:exit_cb(job, status)
  au! flymark
  echohl WarningMsg
  echo "flymark server exited with " .. a:status
  echohl None
endfunc


func s:send() abort
  if exists("b:flymark_tick") && b:flymark_tick == b:changedtick | return | endif
  let b:flymark_tick = b:changedtick
  call ch_sendraw(s:job, json_encode([
        \ getline(1, "$")->join("\n"),
        \ expand("%:p:h"),
        \ ]) .. "\n")
endfunc
