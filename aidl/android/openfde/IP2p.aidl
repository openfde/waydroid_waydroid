package android.openfde;

interface IP2p {
    /**
     * P2P features exposed by wpa_supplicant/chip.
     */
    /* Support for P2P2 (Wi-Fi Alliance P2P v2.0) */
    const long P2P_FEATURE_V2 = 1 << 0;

    /* Support for WPA3 Compatibility Mode in PCC Mode */
    const long P2P_FEATURE_PCC_MODE_WPA3_COMPATIBILITY = 1 << 1;
    
    void addBonjourService(in byte[] query, in byte[] response);
    void p2p_find(in String args);
    void addGroup(in boolean persistent, in int persistentNetworkId);
    void cancelConnect();

    void p2p_stop_find();
    void p2p_asp_provision(in String args);
    void p2p_asp_provision_resp(in String args);
    void p2p_connect(in String args);
    void p2p_listen(in String args);
    void p2p_group_remove(in String ifname);
    void p2p_group_member(in String ifname);
    void p2p_prov_disc(in String args);

    String p2p_get_passphrase();
    String p2p_serv_disc_req(in String args);
    void p2p_serv_disc_cancel(in String identifier);
    void p2p_serv_disc_resp(in String args);

    void p2p_service_update();
    void p2p_serv_disc_external(in String value);
    void p2p_service_flush();
    void p2p_service_rep(in String args);
    void p2p_service_del(in String args);

    void p2p_reject(in String peer);
    void p2p_invite(in String args);
    String p2p_peers();
    String p2p_peer(in String peer);

    void p2p_set(in String args);
    void p2p_flush();
    void p2p_unauthorize(in String peer);
    void p2p_presence_req(in String args);
    void p2p_ext_listen(in String args);
    void p2p_remove_client(in String args);

    boolean registerCallback(in IBInder callback);
    boolean unregisterCallback(in IBinder callback);
    String p2p_get_device_address();
}
