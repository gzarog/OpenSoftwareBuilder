VERSION ?= dev
BINARY = osb
LDFLAGS = -ldflags "-X github.com/gzarog/opensoftwarebuilder/internal/cli.Version=$(VERSION)"

.PHONY: build test vet clean all

all: vet test build

build:
	go build $(LDFLAGS) -o $(BINARY) ./cmd/osb/

test:
	go test ./tests/unit/... -v

vet:
	go vet ./...

clean:
	rm -f $(BINARY) osb-*

cross:
	GOOS=linux GOARCH=amd64 go build $(LDFLAGS) -o osb-linux-amd64 ./cmd/osb/
	GOOS=linux GOARCH=arm64 go build $(LDFLAGS) -o osb-linux-arm64 ./cmd/osb/
	GOOS=darwin GOARCH=amd64 go build $(LDFLAGS) -o osb-darwin-amd64 ./cmd/osb/
	GOOS=darwin GOARCH=arm64 go build $(LDFLAGS) -o osb-darwin-arm64 ./cmd/osb/
	GOOS=windows GOARCH=amd64 go build $(LDFLAGS) -o osb-windows-amd64.exe ./cmd/osb/
	GOOS=windows GOARCH=arm64 go build $(LDFLAGS) -o osb-windows-arm64.exe ./cmd/osb/
