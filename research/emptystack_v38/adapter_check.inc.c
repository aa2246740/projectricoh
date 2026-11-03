unsigned long adapter_checks(void)
{
    unsigned count,cur,previous,physical;
    unsigned long cases=0;
    for(count=1;count<=33;++count)for(cur=0;cur<count;++cur)for(previous=0;previous<=256;++previous){
        KvUiWindow window;
        assert(!kv_ui_window(count,cur,previous==256?UINT_MAX:previous,&window));
        for(physical=0;physical<8;++physical){
            int delta=physical==(window.cursor+1u)%8u?1:physical==(window.cursor+7u)%8u?-1:0;
            unsigned expected=(unsigned)(((int)cur+delta+(int)count)%(int)count);
            n.ui.screen=UV_GROUP;n.ui.count=count;n.ui.cur=cur;n.ui.physical=window.cursor;n.ui.armed=1;
            assert(uv_move(physical)==ENG_OK);
            assert(n.ui.cur==expected&&n.ui.last_cur==cur&&n.ui.physical==physical&&!n.ui.armed);
            ++cases;
        }
    }
    return cases;
}
