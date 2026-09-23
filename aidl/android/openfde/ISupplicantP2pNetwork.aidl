package android.openfde;

interface ISupplicantP2pNetwork {
    String getBssid();

    // Comma or space separated P2P device addresses.
    String getClientList();

    int getId();

    String getInterfaceName();

    String getSsid();

    int getType();

    boolean isCurrent();

    boolean isGroupOwner();

    boolean isPersistent();

    void setClientList(in String clients);
}