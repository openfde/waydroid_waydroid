package android.openfde;

oneway interface IP2pCallback {
    // String-only event channel. data is a JSON object with event and args fields.
    void onEvents(int what, in String data);
}
