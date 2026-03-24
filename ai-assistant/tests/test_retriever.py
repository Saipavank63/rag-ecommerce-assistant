import pytest
from unittest.mock import MagicMock, patch

from src.config import settings
from src.rag.retriever import HybridRetriever


@pytest.fixture
def retriever():
    return HybridRetriever()


class TestHybridRetriever:
    def test_initial_state(self, retriever):
        assert retriever._client is None
        assert retriever._index is None

    def test_is_connected_returns_false_when_no_client(self, retriever):
        assert retriever.is_connected() is False

    @patch("src.rag.retriever.weaviate.connect_to_custom")
    def test_get_client_creates_connection(self, mock_connect, retriever):
        mock_client = MagicMock()
        mock_client.is_connected.return_value = True
        mock_connect.return_value = mock_client

        client = retriever._get_client()

        assert client is mock_client
        mock_connect.assert_called_once()

    @patch("src.rag.retriever.weaviate.connect_to_custom")
    def test_get_client_reuses_existing_connection(self, mock_connect, retriever):
        mock_client = MagicMock()
        mock_client.is_connected.return_value = True
        mock_connect.return_value = mock_client

        client1 = retriever._get_client()
        client2 = retriever._get_client()

        assert client1 is client2
        mock_connect.assert_called_once()

    @patch("src.rag.retriever.weaviate.connect_to_custom")
    def test_get_client_reconnects_if_disconnected(self, mock_connect, retriever):
        disconnected = MagicMock()
        disconnected.is_connected.return_value = False

        reconnected = MagicMock()
        reconnected.is_connected.return_value = True

        mock_connect.side_effect = [disconnected, reconnected]

        retriever._get_client()
        retriever._client = disconnected  # simulate disconnect
        client = retriever._get_client()

        assert client is reconnected
        assert mock_connect.call_count == 2

    def test_close_clears_client(self, retriever):
        mock_client = MagicMock()
        retriever._client = mock_client

        retriever.close()

        mock_client.close.assert_called_once()
        assert retriever._client is None

    def test_close_noop_when_no_client(self, retriever):
        retriever.close()  # should not raise


class TestRetrieverConfig:
    def test_default_settings(self):
        assert settings.similarity_top_k == 5
        assert 0.0 <= settings.hybrid_alpha <= 1.0
