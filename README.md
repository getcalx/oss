# getcalx (Deprecated)

**This package is deprecated.** Calx has moved to a cloud-hosted model.

Visit **[calx.sh](https://calx.sh)** for the new setup.

## What happened?

The local SDK (`getcalx`) has been retired. Calx now runs as a cloud-hosted service with API key authentication. The local SQLite backend, MCP server, and CLI tools from this package are no longer maintained.

## If you're currently using getcalx

1. Visit [calx.sh](https://calx.sh) to set up the cloud-hosted version.
2. Pin your current version in `requirements.txt` if you need to keep using the local SDK temporarily. Yanked releases are still installable by pinned version.
3. The cloud-hosted version provides the same correction capture, recurrence detection, and rule compilation -- without local infrastructure.

## If you just installed this package

You probably want the cloud version instead. Uninstall this package and visit [calx.sh](https://calx.sh):

```bash
pip uninstall getcalx
```

## License

MIT
